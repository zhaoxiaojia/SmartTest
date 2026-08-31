from types import SimpleNamespace

import pytest
from requests import HTTPError

from core.confluence.models import ConfluencePage
from core.confluence.project import ProjectDetails
from smarttest_web.confluence.project_repository import ConfluenceProjectRepository
from smarttest_web.project_facts_api import ProjectFactsWebOwner
from smarttest_web.audit.confluence_adapter import WebConfluenceAuditOwner
from test_resource_access import contexts


class CatalogClient:
    def __init__(self, account, denied=()):
        self.account, self.denied = account, denied

    def get_page_by_url(self, url):
        space = url.split('/display/')[1].split('/')[0]
        if space in self.denied:
            raise HTTPError(response=SimpleNamespace(status_code=403))
        row = (f'<tr><td><a href="/pages/viewpage.action?pageId={space}">{space}</a></td>'
               f'<td>{space}</td><td>{self.account}</td></tr>')
        return ConfluencePage('catalog-'+space, 'Project Space', url, view_body=
            '<table><tr><th>Page</th><th>Project ID</th><th>ODM</th></tr>'+row+'</table>')


def test_confluence_account_catalog_refresh_and_403_keep_single_shared_data(tmp_path):
    database, sessions, first, second = contexts(tmp_path)
    alice = sessions.resource_access(first, 'confluence:test', database)
    bob = sessions.resource_access(second, 'confluence:test', database)
    owner = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database),
        client_factory=lambda account, _: CatalogClient(account, ('TV',) if account == 'bob' else ()))
    owner.refresh(alice, 'test')
    assert owner.query(bob)['projects'] == []
    owner.refresh(bob, 'test')
    assert {row['project_id'] for row in owner.query(alice)['projects']} == {'TV', 'DOPL', 'OOPL', 'SDPL'}
    assert {row['project_id'] for row in owner.query(bob)['projects']} == {'DOPL', 'OOPL', 'SDPL'}
    with database.connect() as connection:
        assert connection.execute('SELECT count(*) FROM confluence_projects').fetchone()[0] == 4
    with pytest.raises(PermissionError, match='permission_denied'):
        owner._service(bob, 'test').get_project('TV', ProjectDetails(roles=True))


def test_review_selection_cannot_bypass_account_catalog(tmp_path):
    database, sessions, first, second = contexts(tmp_path)
    alice = sessions.resource_access(first, 'confluence:test', database)
    bob = sessions.resource_access(second, 'confluence:test', database)
    facts = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database), client_factory=lambda account, _: CatalogClient(account))
    facts.refresh(alice, 'test')
    owner = WebConfluenceAuditOwner(*facts.audit_dependencies(bob, 'test'), access=bob)
    with pytest.raises(PermissionError, match='permission_denied'):
        owner.resolve({'projectIds': ['TV'], 'startDate': '2026-08-17', 'endDate': '2026-08-24'})


def test_catalog_403_revokes_existing_account_scope_without_deleting_shared_projects(tmp_path):
    database, sessions, first, second = contexts(tmp_path)
    alice = sessions.resource_access(first, 'confluence:test', database)
    bob = sessions.resource_access(second, 'confluence:test', database)
    client = CatalogClient('alice')
    owner = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database), client_factory=lambda *_: client)
    owner.refresh(alice, 'test')
    owner.refresh(bob, 'test')
    client.denied = ('TV',)
    owner.refresh(alice, 'test')
    restored = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database))
    assert {row['project_id'] for row in restored.query(alice)['projects']} == {'SDPL', 'DOPL', 'OOPL'}
    assert len(restored.query(bob)['projects']) == 4
    assert restored._repository.get('TV', ProjectDetails()) is not None


def test_valid_empty_catalog_is_ready_after_owner_restart(tmp_path):
    database, sessions, first, second = contexts(tmp_path)
    alice = sessions.resource_access(first, 'confluence:test', database)
    bob = sessions.resource_access(second, 'confluence:test', database)
    class Empty(CatalogClient):
        def get_page_by_url(self, url):
            return ConfluencePage('catalog', 'Project Space', url, view_body=
                '<table><tr><th>Page</th><th>Project ID</th></tr></table>')
    owner = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database), client_factory=lambda *_: Empty('alice'))
    owner.refresh(alice, 'test')
    restored = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database))
    assert restored.query(alice)['state'] == 'ready'
    assert restored.query(alice)['projects'] == []
    assert restored.query(bob)['state'] == 'no_snapshot'


@pytest.mark.parametrize('status', [401, 403])
def test_detail_failure_preserves_shared_cache_and_revokes_only_denied_section(tmp_path, status):
    from test_confluence_cache_service import ConfluenceGateway, _row
    from core.confluence.project_mapper import ConfluenceProjectMapper
    from smarttest_web.confluence.cache_service import ConfluenceProjectCacheService
    database, sessions, first, second = contexts(tmp_path)
    repo = ConfluenceProjectRepository(database)
    mapper = ConfluenceProjectMapper()
    repo.save_core((mapper.from_catalog(_row()),))
    alice = sessions.resource_access(first, 'confluence:test', database)
    bob = sessions.resource_access(second, 'confluence:test', database)
    for access in (alice, bob):
        access.publish((('project', 'P100', 'catalog', 'DOPL'),), lambda: None)
    service = ConfluenceProjectCacheService(ConfluenceGateway(), mapper, repo, access=alice)
    service.refresh_project('P100', ProjectDetails(roles=True))
    class Denied(ConfluenceGateway):
        def load_project_sections(self, *_): raise HTTPError(response=SimpleNamespace(status_code=status))
    other = ConfluenceProjectCacheService(Denied(), mapper, repo, access=bob)
    with pytest.raises(PermissionError, match='reauthentication_required' if status == 401 else 'permission_denied'):
        other.refresh_project('P100', ProjectDetails(roles=True))
    assert bob.allows('project', 'P100', 'catalog')
    assert not bob.allows('project', 'P100', 'roles')
    assert service.read_project('P100', ProjectDetails(roles=True)).roles.value[0].people[0].display_name == 'Alice'


def test_partial_catalog_does_not_revoke_previous_confirmed_resources(tmp_path):
    from test_confluence_cache_service import ConfluenceGateway, _row
    from core.confluence.project import ProjectSyncScope
    from core.confluence.project_mapper import ConfluenceProjectMapper
    from smarttest_web.confluence.cache_service import ConfluenceProjectCacheService
    database, sessions, first, _ = contexts(tmp_path)
    access = sessions.resource_access(first, 'confluence:test', database)
    repo = ConfluenceProjectRepository(database)
    class Gateway(ConfluenceGateway):
        def refresh_project_catalogs(self, _):
            return {'projects': [_row(), {'space_key': 'DOPL'}], 'complete_spaces': ['DOPL']}
    access.publish((('project', 'old', 'catalog', 'DOPL'),), lambda: None)
    cache = ConfluenceProjectCacheService(Gateway(), ConfluenceProjectMapper(), repo, access=access)
    cache.refresh_projects(ProjectSyncScope())
    assert 'old' in access.ids('project', 'catalog')


def test_actual_malformed_catalog_is_not_published_as_confirmed_empty_scope(tmp_path):
    database, sessions, first, _ = contexts(tmp_path)
    access = sessions.resource_access(first, 'confluence:test', database)
    repo = ConfluenceProjectRepository(database)
    client = CatalogClient('alice')
    owner = ProjectFactsWebOwner(repository=repo, client_factory=lambda *_: client)
    owner.refresh(access, 'test')
    class Malformed(CatalogClient):
        def get_page_by_url(self, url):
            return ConfluencePage('catalog', 'Project Space', url, view_body='<p>missing table</p>')
    owner._client_factory = lambda *_: Malformed('alice')
    with pytest.raises(RuntimeError, match='remote_unavailable'):
        owner.refresh(access, 'test')
    restored = ProjectFactsWebOwner(repository=ConfluenceProjectRepository(database))
    assert len(restored.query(access)['projects']) == 4


def test_page_mapping_replacement_and_403_remove_only_account_page_proof(tmp_path):
    from conftest import confirmed_access
    from test_manual_audit_adapters import _discovery_cache, _audit_token
    repository, client, cache = _discovery_cache(tmp_path)
    cache.refresh_project('P1', ProjectDetails(roles=True, evidence=True))
    alice = cache._access
    bob = confirmed_access(repository.database, ('P1',), ('14',), account='bob')
    owner = WebConfluenceAuditOwner(cache, repository, client, access=alice)
    owner.load_current_page('14', _audit_token())
    del client.pages['14']
    cache.refresh_project('P1', ProjectDetails(evidence=True))
    assert not alice.allows('page', '14', 'metadata')
    assert not alice.allows('page', '14', 'body')
    assert bob.allows('page', '14', 'metadata')
    assert '14' not in {item.page.page_id for item in cache.read_project('P1', ProjectDetails(evidence=True)).evidence.value}
    assert '14' in {item.page.page_id for item in repository.get('P1', ProjectDetails(evidence=True)).evidence.value}
