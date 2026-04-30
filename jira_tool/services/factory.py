from __future__ import annotations

from pathlib import Path

from AI.mcp.context import McpContextService, create_default_mcp_context_service
from jira_tool.auth.basic import JiraBasicAuth
from jira_tool.cache.metadata_cache import JiraFieldMetadataCache
from jira_tool.fields.registry import FieldRegistry
from jira_tool.services.ai_analysis_service import JiraAIAnalysisService, create_default_jira_ai_analysis_service
from jira_tool.services.issue_service import JiraIssueService
from jira_tool.services.workspace import JiraWorkspaceService
from jira_tool.transport.client import JiraClient, JiraClientConfig

def create_jira_workspace_service(
    *,
    base_url: str,
    username: str,
    password: str,
    cache_dir: str | Path,
    page_size: int = 100,
    max_workers: int = 6,
    metadata_ttl_seconds: float = 3600,
    ai_service: JiraAIAnalysisService | None = None,
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
    return JiraWorkspaceService(
        base_url=base_url,
        issue_service=JiraIssueService(client, registry=jira_registry),
        ai_service=ai_service or create_default_jira_ai_analysis_service(),
        mcp_context_service=mcp_context_service
        or create_default_mcp_context_service(username=username, password=password),
    )
