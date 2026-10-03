# MCP Guardian demo fixture — inert test target, never executed, not real malware.
"""clean-greeter — a genuinely safe MCP server fixture.

Two read-only tools (greet, echo) with explicit readOnlyHint annotations.
No dynamic execution, no shell access, no secret handling, no network.
Scanned by MCP Guardian in the demo to show the green/allow path.
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clean-greeter")


@mcp.tool(
    name="greet",
    annotations={"readOnlyHint": True, "title": "Greet"},
    description="Return a friendly greeting for the given name.",
)
def greet(name: str) -> str:
    """Return a friendly greeting for the given name."""
    return f"Hello, {name}! Welcome to MCP Guardian."


@mcp.tool(
    name="echo",
    annotations={"readOnlyHint": True, "title": "Echo"},
    description="Echo the provided text back unchanged.",
)
def echo(text: str) -> str:
    """Echo the provided text back unchanged."""
    return text


if __name__ == "__main__":
    mcp.run()
