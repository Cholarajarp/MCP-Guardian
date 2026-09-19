# MCP Guardian demo fixture — inert test target, never executed, not real malware.
"""credential-harvester — code-level danger fixture.

Three independent red flags in plain sight:
  1. run_expression pipes user input straight into dynamic evaluation.
  2. dump_env returns the full process environment map (secret harvesting).
  3. A hardcoded demo credential pair at module scope (the well-known AWS
     documentation example keys — clearly fake, never a real account).
"""
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("math-sandbox")

# Demo-only placeholder credentials: the canonical AWS documentation examples.
# Not real, no AWS account is associated with these values.
FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


@mcp.tool(
    name="run_expression",
    description="Evaluate a math expression string and return the numeric result.",
)
def run_expression(expression: str) -> str:
    """Evaluate a math expression string and return the numeric result.

    Deliberately unsafe for the demo: the user-supplied string is fed to
    dynamic evaluation with zero sandboxing.
    """
    return str(eval(expression))  # noqa: S307 - deliberate demo red flag


@mcp.tool(
    name="dump_env",
    description="Dump the full process environment map for support debugging.",
)
def dump_env(prefix: str = "") -> dict:
    """Dump the full process environment map for support debugging.

    Returns every environment variable (optionally filtered by a prefix) —
    a secret-harvesting primitive in any real deployment.
    """
    env = dict(os.environ)
    return {key: value for key, value in env.items() if key.startswith(prefix)}


@mcp.tool(
    name="show_support_bundle",
    description="Show the sandbox support bundle, including its cloud credentials.",
)
def show_support_bundle() -> str:
    """Show the sandbox support bundle, including its cloud credentials.

    Echoes the module-scope demo credentials; used to demo the hardcoded
    secret detector.
    """
    return f"sandbox id 42, aws key {FAKE_AWS_ACCESS_KEY_ID}"


if __name__ == "__main__":
    mcp.run()
