from AI.mcp.client import McpTool
from AI.mcp.context import McpContextService, _account_name


class _FakeClient:
    name = "soc_spec_search"
    context_enabled = True

    def __init__(self):
        self.calls = []

    def list_tools(self):
        return [
            McpTool(
                server_name=self.name,
                name="search_spec",
                description="Search SoC spec by keyword",
                input_schema={"properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}},
            )
        ]

    def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return {"content": [{"type": "text", "text": "w2l is related to Wi-Fi"}]}


def test_mcp_context_searches_internal_terms() -> None:
    client = _FakeClient()
    service = McpContextService([client])

    context = service.enrich("analyze w2l bugs")

    assert client.calls[0] == ("search_spec", {"query": "w2l", "limit": 5})
    assert context[0]["server"] == "soc_spec_search"
    assert context[0]["query"] == "w2l"
    assert "Wi-Fi" in context[0]["result"][0]["text"]


def test_account_name_removes_domain() -> None:
    assert _account_name("AMLOGIC\\chao.li") == "chao.li"
    assert _account_name("chao.li@amlogic.com") == "chao.li"
