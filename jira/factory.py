from __future__ import annotations

from pathlib import Path

from AI.mcp.context import McpContextService, create_default_mcp_context_service
from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.cache.metadata_cache import JiraFieldMetadataCache
from support.jira_integration.fields.registry import FieldRegistry
from jira.analysis_service import JiraAnalysisService
from jira.browse_service import JiraBrowseService
from support.jira_integration.services.issue_service import JiraIssueService
from jira.workspace import JiraWorkspaceService
from support.jira_integration.transport.client import JiraClient, JiraClientConfig

def create_jira_workspace_service(
    *,
    base_url: str,
    username: str,
    password: str,
    cache_dir: str | Path,
    page_size: int = 100,
    max_workers: int = 6,
    metadata_ttl_seconds: float = 3600,
    mcp_context_service: McpContextService | None = None,
) -> JiraWorkspaceService:
    auth = JiraBasicAuth(username=username, password=password)
    client = JiraClient(
        JiraClientConfig(
            base_url=base_url,
            page_size=page_size,
            max_workers=max_workers,
        ),
        auth,
    )
    metadata_cache = JiraFieldMetadataCache(Path(cache_dir) / "field_metadata.db")
    jira_registry = FieldRegistry.bootstrap_from_client(
        client,
        metadata_cache=metadata_cache,
        ttl_seconds=metadata_ttl_seconds,
    )
    issue_service = JiraIssueService(client, registry=jira_registry)
    browse_service = JiraBrowseService(base_url=base_url, issue_service=issue_service)
    analysis_service = JiraAnalysisService(
        base_url=base_url,
        issue_service=issue_service,
        mcp_context_service=mcp_context_service
        or create_default_mcp_context_service(username=username, password=password),
    )
    return JiraWorkspaceService(
        browse_service=browse_service,
        analysis_service=analysis_service,
    )
