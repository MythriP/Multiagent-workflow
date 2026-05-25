"""Shared filesystem path resolution for the script_agent package.

All runtime LLM prompts live in `<repo>/.claude/prompts/` so the agent
harness and the Python pipeline share one source of truth. Modules
import `PROMPTS_DIR` from here rather than reaching into the package
directory.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PACKAGE_DIR.parent

PROMPTS_DIR: Path = REPO_ROOT / ".claude" / "prompts"

DEFAULT_OUTPUTS_DIR: Path = PACKAGE_DIR / "outputs"
DEFAULT_CACHE_DIR: Path = PACKAGE_DIR / "cache"
DEFAULT_LOGS_DIR: Path = PACKAGE_DIR / "logs"

__all__ = [
    "PACKAGE_DIR",
    "REPO_ROOT",
    "PROMPTS_DIR",
    "DEFAULT_OUTPUTS_DIR",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_LOGS_DIR",
]
