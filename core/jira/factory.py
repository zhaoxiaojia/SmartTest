from __future__ import annotations

from pathlib import Path

from core.jira.mcp_context import McpContextService, create_default_mcp_context_service
from core.jira.gateway import JiraGateway
from core.jira.cache.metadata_cache import JiraFieldMetadataCache
from core.jira.fields.registry import FieldRegistry
from core.jira.analysis_service import JiraAnalysisService
from core.jira.browse_service import JiraBrowseService
from core.jira.services.issue_service import JiraIssueService
from core.jira.workspace import JiraWorkspaceService

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
    client = JiraGateway(
        base_url,
        username,
        password,
        page_size=page_size,
        max_workers=max_workers,
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
