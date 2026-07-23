from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Iterable

from support.jira_integration.core.description import render_notes_description
from support.jira_integration.core.models import (
    CreateIssueResult,
    ExistingIssue,
)
from tool.SmartHome.redmine.clone_draft import (
    CloneDraft,
    RedmineCloneDraftService,
)
from tool.SmartHome.redmine.mapping import redmine_tracker_to_jira_type


@dataclass(frozen=True)
class CloneBatchSnapshot:
    state: str
    selected_ids: tuple[str, ...]
    drafts: tuple[dict[str, Any], ...]
    loaded: int
    total: int
    error: str
    first_invalid_issue_id: str
    first_invalid_field_id: str


@dataclass(frozen=True)
class CloneOperation:
    generation: int
    kind: str
    awaitable: Awaitable[Any]


class RedmineCloneController:
    """Own the Redmine clone batch state machine and Jira create orchestration."""

    def __init__(
        self,
        issue_controller,
        *,
        jira_dependencies: Callable[[], tuple[Any, Any, Any]] | None = None,
        account: Callable[[], str] | None = None,
        identity: Callable[[str, dict[str, Any]], tuple[str, dict[str, str]]]
        | None = None,
        load_detail: Callable[[Any], Awaitable[Any]] | None = None,
        download_attachments: Callable[[Iterable[Any]], Awaitable[Iterable[Any]]]
        | None = None,
        draft_service: RedmineCloneDraftService | None = None,
        prepare_records: Callable[[], Awaitable[Any]] | None = None,
        submit_records: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = None,
        search_users: Callable[[str, str, str], Awaitable[Any]] | None = None,
    ):
        self._issue_controller = issue_controller
        self._jira_dependencies = jira_dependencies or (lambda: (None, None, None))
        self._account = account or (lambda: "")
        self._identity = identity or (lambda _account, _user: ("", {}))
        self._load_detail = load_detail
        self._download_attachments = download_attachments
        self._draft_service = draft_service or RedmineCloneDraftService()
        self._prepare_records_override = prepare_records
        self._submit_records_override = submit_records
        self._search_users_override = search_users
        self._generation = 0
        self._state = "idle"
        self._selected_ids: list[str] = []
        self._records: list[dict[str, Any]] = []
        self._loaded = 0
        self._total = 0
        self._error = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        self._user_options: dict[tuple[str, str], list[dict[str, Any]]] = {}

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def snapshot(self) -> CloneBatchSnapshot:
        return CloneBatchSnapshot(
            state=self._state,
            selected_ids=tuple(self._selected_ids),
            drafts=tuple(self._record_payload(item) for item in self._records),
            loaded=self._loaded,
            total=self._total,
            error=self._error,
            first_invalid_issue_id=self._first_invalid_issue_id,
            first_invalid_field_id=self._first_invalid_field_id,
        )

    def reset(self) -> None:
        self._generation += 1
        self._state = "idle"
        self._selected_ids = []
        self._records = []
        self._loaded = 0
        self._total = 0
        self._error = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        self._user_options = {}

    def begin_selection(self) -> bool:
        if self._state != "idle":
            return False
        self._state = "selecting"
        self._selected_ids = []
        self._error = ""
        return True

    def toggle_selection(
        self, issue_id: str, selected: bool, rows: Iterable[dict[str, Any]]
    ) -> bool:
        if self._state != "selecting":
            return False
        issue_id = str(issue_id or "").strip()
        rows = list(rows)
        row = next(
            (
                item
                for item in rows
                if str(item.get("id") or item.get("key") or "") == issue_id
            ),
            None,
        )
        if row is None or row.get("cloneStatus") == "cloned":
            return False
        selected_ids = set(self._selected_ids)
        if selected:
            selected_ids.add(issue_id)
        else:
            selected_ids.discard(issue_id)
        self._selected_ids = [
            str(item.get("id") or item.get("key") or "")
            for item in rows
            if str(item.get("id") or item.get("key") or "") in selected_ids
        ]
        return True

    def cancel_selection(self) -> bool:
        if self._state != "selecting":
            return False
        self.reset()
        return True

    def start_prepare(self) -> CloneOperation | None:
        if self._state not in ("selecting", "prepare_failed") or not self._selected_ids:
            return None
        self._state = "loading"
        self._records = []
        self._loaded = 0
        self._total = len(self._selected_ids)
        self._error = ""
        awaitable = (
            self._prepare_records_override()
            if self._prepare_records_override is not None
            else self._prepare_records()
        )
        return self._operation("prepare", awaitable)

    def update_draft(self, issue_id: str, field_id: str, value: Any) -> bool:
        if self._state != "editing":
            return False
        record = self._record(issue_id)
        if record is None:
            return False
        try:
            record["draft"].update(str(field_id or ""), value)
        except (KeyError, TypeError, ValueError) as exc:
            record["error"] = str(exc)
            record["errorFieldId"] = str(field_id or "")
        else:
            record["error"] = ""
            record["errorFieldId"] = ""
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        return True

    def start_submit(self) -> CloneOperation | None:
        if self._state != "editing":
            return None
        self._state = "validating"
        self._first_invalid_issue_id = ""
        self._first_invalid_field_id = ""
        for record in self._records:
            if record["error"]:
                self._first_invalid_issue_id = record["draft"].source_id
                self._first_invalid_field_id = record["errorFieldId"]
                self._state = "editing"
                return None
            errors = record["draft"].errors
            if errors:
                self._first_invalid_issue_id = record["draft"].source_id
                self._first_invalid_field_id = errors[0].field_id
                self._state = "editing"
                return None
        return self._start_submit_records(self._records)

    def retry_failed(self) -> CloneOperation | None:
        if self._state != "partial_failed":
            return None
        failed = [item for item in self._records if item["state"] == "failed"]
        return self._start_submit_records(failed) if failed else None

    def close_batch(self) -> bool:
        if self._state == "submitting":
            return False
        selected_ids = list(self._selected_ids)
        completed = self._state == "completed"
        self.reset()
        if not completed:
            self._state = "selecting"
            self._selected_ids = selected_ids
        return True

    def start_user_search(
        self, issue_id: str, field_id: str, query: str
    ) -> CloneOperation | None:
        if self._state != "editing" or self._record(issue_id) is None:
            return None
        awaitable = (
            self._search_users_override(issue_id, field_id, query)
            if self._search_users_override is not None
            else self._search_users(issue_id, field_id, query)
        )
        return self._operation("users", awaitable)

    def apply_error(self, kind: str, error: Exception) -> None:
        self._error = str(error)
        if kind == "prepare":
            self._records = []
            self._loaded = 0
            self._state = "prepare_failed"
        elif kind == "submit":
            self._state = "partial_failed"

    def apply_result(self, kind: str, result: Any) -> None:
        if kind == "prepare":
            records, display_names = result
            self._records = list(records)
            for record in self._records:
                draft = record["draft"]
                for field in draft.fields:
                    account = (
                        str(field.value or "")
                        if field.schema.control.value == "user"
                        else ""
                    )
                    if account:
                        self._user_options[(draft.source_id, field.field_id)] = [
                            {
                                "value": account,
                                "label": display_names.get(account, account),
                                "avatarUrl": "",
                                "children": [],
                            }
                        ]
            self._loaded = len(self._records)
            self._state = "editing"
            return
        if kind == "users":
            issue_id, field_id, users = result
            existing = self._user_options.get((issue_id, field_id), [])
            fetched = [
                {
                    "value": str(item.get("account") or ""),
                    "label": str(item.get("display_name") or ""),
                    "avatarUrl": str(item.get("avatar_url") or ""),
                    "children": [],
                }
                for item in users
            ]
            fetched_values = {str(item.get("value") or "") for item in fetched}
            self._user_options[(issue_id, field_id)] = fetched + [
                item
                for item in existing
                if str(item.get("value") or "") not in fetched_values
            ]
            return
        if kind == "submit":
            self._apply_submit_result(result)

    def _operation(self, kind: str, awaitable: Awaitable[Any]) -> CloneOperation:
        self._generation += 1
        return CloneOperation(self._generation, kind, awaitable)

    def _start_submit_records(
        self, records: list[dict[str, Any]]
    ) -> CloneOperation:
        self._state = "submitting"
        self._loaded = 0
        self._total = len(records)
        self._error = ""
        awaitable = (
            self._submit_records_override(records)
            if self._submit_records_override is not None
            else self._submit_records(records)
        )
        return self._operation("submit", awaitable)

    async def _prepare_records(self):
        jira_client, _create_service, schema_service = self._jira_dependencies()
        if jira_client is None or schema_service is None:
            raise RuntimeError("Jira credentials are unavailable")
        account = str(self._account() or "").strip()
        current_user = jira_client.current_user()
        reporter = str(current_user.get("account") or "").strip()
        if not reporter:
            raise RuntimeError("Current Jira reporter identity is unavailable")
        department, display_names = self._identity(account, current_user)
        records = []
        schemas = {}
        for issue_id in self._selected_ids:
            source = self._issue_controller.source_for_issue(issue_id)
            project, item, detail = source.project, source.item, source.detail
            if project is None or item is None:
                raise RuntimeError(f"Redmine issue {issue_id} is unavailable")
            if detail is None:
                if self._load_detail is None:
                    raise RuntimeError(f"Redmine issue {issue_id} detail is unavailable")
                detail = await self._load_detail(source)
            issue_type = redmine_tracker_to_jira_type(detail.tracker)
            if issue_type not in schemas:
                schemas[issue_type] = schema_service.schema("SH", issue_type)
                attachment_fields = [
                    field
                    for field in schemas[issue_type]
                    if str(field.name or "").strip().casefold() == "attachment links"
                ]
                if len(attachment_fields) != 1:
                    raise RuntimeError(
                        "Jira create schema must contain exactly one Attachment links field"
                    )
            clone_draft = self._draft_service.build(
                issue=detail,
                project=project,
                schema=schemas[issue_type],
                account=reporter,
                department=department,
                prepared_description=render_notes_description(detail.description),
            )
            records.append(_new_record(clone_draft))
        return records, display_names

    async def _submit_records(self, records: list[dict[str, Any]]):
        _client, create_service, _schema_service = self._jira_dependencies()
        if create_service is None:
            raise RuntimeError("Jira credentials are unavailable")
        results = []
        for record in records:
            clone_draft = record["draft"]
            try:
                request = clone_draft.to_request()
                if clone_draft.source_attachments:
                    if self._download_attachments is None:
                        raise RuntimeError("Redmine attachment downloader is unavailable")
                    attachments = await self._download_attachments(
                        clone_draft.source_attachments
                    )
                    request = replace(request, attachments=tuple(attachments))
                existing = create_service.check_issue_by_external_url(
                    project_key="SH", external_url=clone_draft.source_url
                )
                if existing:
                    errors = create_service.sync_attachments(
                        existing.key, request.attachments
                    )
                    payload = CreateIssueResult(
                        created=False,
                        existing_key=existing.key,
                        issue_url=existing.web_url,
                        raw=existing.raw,
                        attachment_errors=errors,
                    )
                    state = "failed" if errors else "duplicate"
                    results.append(
                        (
                            clone_draft.source_id,
                            state,
                            payload,
                            "; ".join(errors),
                        )
                    )
                    continue
                created = create_service.create_issue(request)
                state = (
                    "failed"
                    if created.attachment_errors
                    else ("created" if created.created else "duplicate")
                )
                results.append(
                    (
                        clone_draft.source_id,
                        state,
                        created,
                        "; ".join(created.attachment_errors),
                    )
                )
            except Exception as exc:
                results.append((clone_draft.source_id, "failed", None, str(exc)))
        return results

    async def _search_users(self, issue_id: str, field_id: str, query: str):
        jira_client, _create_service, _schema_service = self._jira_dependencies()
        users = (
            []
            if jira_client is None
            else jira_client.search_users(query, project_key="SH")
        )
        return issue_id, field_id, users

    def _apply_submit_result(self, result) -> None:
        resolved = {}
        for issue_id, state, payload, error in result:
            record = self._record(issue_id)
            if record is None:
                continue
            record["state"] = state
            record["error"] = error
            if isinstance(payload, CreateIssueResult):
                record["key"] = payload.issue_key or payload.existing_key
                record["url"] = payload.issue_url
            if state == "created" and isinstance(payload, CreateIssueResult):
                resolved[issue_id] = ExistingIssue(
                    key=payload.issue_key, web_url=payload.issue_url
                )
            elif state == "duplicate":
                key = getattr(payload, "existing_key", "") or getattr(
                    payload, "key", ""
                )
                url = getattr(payload, "issue_url", "") or getattr(
                    payload, "web_url", ""
                )
                record["key"] = key
                record["url"] = url
                resolved[issue_id] = ExistingIssue(key=key, web_url=url)
        if resolved:
            self._issue_controller.record_clone_results(resolved)
        self._loaded = len(result)
        self._state = (
            "partial_failed"
            if any(item["state"] == "failed" for item in self._records)
            else "completed"
        )

    def _record(self, issue_id: str) -> dict[str, Any] | None:
        issue_id = str(issue_id or "")
        return next(
            (
                item
                for item in self._records
                if item["draft"].source_id == issue_id
            ),
            None,
        )

    def _record_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        clone_draft = record["draft"]
        fields = []
        for field in clone_draft.fields:
            if (
                not field.schema.required
                and field.field_id != "priority"
                and str(field.schema.name or "").strip().casefold()
                != "attachment links"
            ):
                continue
            options = self._user_options.get(
                (clone_draft.source_id, field.field_id),
                [_option_payload(item) for item in field.schema.options],
            )
            fields.append(
                {
                    "fieldId": field.field_id,
                    "name": field.schema.name,
                    "required": field.schema.required,
                    "control": field.schema.control.value,
                    "options": options,
                    "value": field.value,
                    "displayValue": next(
                        (
                            str(item.get("label") or item.get("value") or "")
                            for item in options
                            if str(item.get("value") or "")
                            == str(field.value or "")
                        ),
                        str(field.value or ""),
                    ),
                    "error": field.error,
                }
            )
        return {
            "issueId": clone_draft.source_id,
            "sourceUrl": clone_draft.source_url,
            "fields": fields,
            "errors": [
                {
                    "fieldId": item.field_id,
                    "message": item.message,
                    "blocking": item.blocking,
                }
                for item in clone_draft.errors
            ],
            "state": record["state"],
            "key": record["key"],
            "url": record["url"],
            "error": record["error"],
        }


def _new_record(clone_draft: CloneDraft) -> dict[str, Any]:
    return {
        "draft": clone_draft,
        "state": "editing",
        "key": "",
        "url": "",
        "error": "",
        "errorFieldId": "",
    }


def _option_payload(option) -> dict[str, Any]:
    return {
        "value": option.value,
        "label": option.label,
        "avatarUrl": str(getattr(option, "avatar_url", "") or ""),
        "children": [_option_payload(child) for child in option.children],
    }
