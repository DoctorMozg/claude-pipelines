import os
import shutil
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "mz-handoff" / "scripts"
BASH = shutil.which("bash") or "/bin/bash"
# Every setting the scripts take from their caller, including the ones Claude Code sets when the
# suite runs inside a session; a test sets the ones it needs itself.
CALLER_VARS = frozenset(
    {
        "CLAUDE_PROJECT_DIR",
        "MZ_MEMORY_ROOT",
        "MZ_HANDOFF_AFTER",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CONFIG_DIR",
    }
)


def clean_env() -> dict[str, str]:
    """os.environ without CALLER_VARS, so the developer's shell can't steer a script under test."""
    return {key: value for key, value in os.environ.items() if key not in CALLER_VARS}
