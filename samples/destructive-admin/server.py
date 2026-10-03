# MCP Guardian demo fixture — inert test target, never executed, not real malware.
"""destructive-admin — unannotated destructive tools fixture.

Four admin tools that would irreversibly destroy state if ever run (they
never are — text only). None declares readOnlyHint or destructiveHint, so
an agent has no metadata hint that these are dangerous. One tool also
executes a shell command taken straight from a tool argument.
"""
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("admin-console")


@mcp.tool(
    name="delete_all_users",
    description="Delete every user account in the database. No confirmation prompt.",
)
def delete_all_users() -> str:
    """Delete every user account in the database. No confirmation prompt."""
    return "all users deleted"


@mcp.tool(
    name="flush_cache",
    description="Flush the entire cache cluster immediately.",
)
def flush_cache() -> str:
    """Flush the entire cache cluster immediately."""
    return "cache flushed"


@mcp.tool(
    name="drop_table",
    description="Drop a table from the database by name.",
)
def drop_table(table: str) -> str:
    """Drop a table from the database by name."""
    return f"table {table} dropped"


@mcp.tool(
    name="run_maintenance",
    description="Run a maintenance shell command on the host.",
)
def run_maintenance(command: str) -> str:
    """Run a maintenance shell command on the host.

    Deliberately unsafe for the demo: the tool argument is passed to a
    shell process unsanitized.
    """
    result = subprocess.run(command, shell=True, capture_output=True, text=True)  # noqa: S602 - deliberate demo red flag
    return result.stdout or result.stderr


if __name__ == "__main__":
    mcp.run()
