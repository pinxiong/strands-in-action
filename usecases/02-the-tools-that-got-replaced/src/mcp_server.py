"""A minimal MCP server for E5: one tool over stdio.

mcp 2.x renamed FastMCP to MCPServer (mcp.server.fastmcp raises on import).
"""
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("repo-tools")


@mcp.tool()
def word_count(text: str) -> int:
    """Count the number of words in a piece of text.

    Args:
        text: the text to count words in
    """
    return len(text.split())


if __name__ == "__main__":
    mcp.run(transport="stdio")
