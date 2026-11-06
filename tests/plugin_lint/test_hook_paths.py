import json
import re
from pathlib import Path

import pytest

from .conftest import PLUGINS_DIR

HOOK_CONFIGS = sorted(PLUGINS_DIR.glob("*/hooks/hooks.json"))
# Anthropic's directory follows a hook's command into plain shell scripts and refuses one whose
# paths the shell computes, or that runs a program it can't read (COMMAND_PATH_COMPUTED).
PLUGIN_PATH = re.compile(r'\$\{CLAUDE_PLUGIN_ROOT\}"?/(?P<path>[\w./-]+)')
COMPUTED_ROOT = re.compile(r'BASH_SOURCE|dirname "?\$0')
INTERPRETER = re.compile(r"(?<![\w./-])(?:g?awk|mawk|perl|python3?|node|ruby)(?=\s)")


def _commands(config: Path) -> list[str]:
    hooks = json.loads(config.read_text(encoding="utf-8"))["hooks"]
    return [
        handler["command"]
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
        if handler.get("type") == "command"
    ]


def _code_lines(script: Path) -> list[str]:
    """Non-comment lines, each joined with its backslash continuations."""
    joined = script.read_text(encoding="utf-8").replace("\\\n", " ")
    return [line for line in joined.splitlines() if not line.lstrip().startswith("#")]


def _reached_scripts(config: Path) -> dict[Path, list[str]]:
    """Every file a hook command reaches through ${CLAUDE_PLUGIN_ROOT} paths, and its code lines."""
    plugin = config.parents[1]
    pending = [plugin / m["path"] for c in _commands(config) for m in PLUGIN_PATH.finditer(c)]
    reached: dict[Path, list[str]] = {}
    while pending:
        path = pending.pop()
        if path in reached or not path.is_file() or path.suffix != ".sh":
            reached.setdefault(path, [])
            continue
        reached[path] = _code_lines(path)
        pending += [
            plugin / m["path"] for line in reached[path] for m in PLUGIN_PATH.finditer(line)
        ]
    return reached


def _inline_program(line: str) -> bool:
    """True when an interpreter on this line gets a quoted program rather than a plugin file."""
    for match in INTERPRETER.finditer(line):
        rest = line[match.end() :]
        quote, root = rest.find("'"), rest.find("${CLAUDE_PLUGIN_ROOT}")
        if quote != -1 and (root == -1 or quote < root):
            return True
    return False


@pytest.mark.parametrize("config", HOOK_CONFIGS, ids=lambda path: path.parents[1].name)
class TestHookReachedScripts:
    def test_every_plugin_path_exists(self, config: Path) -> None:
        missing = sorted(
            path.relative_to(PLUGINS_DIR).as_posix()
            for path in _reached_scripts(config)
            if not path.is_file()
        )
        assert missing == []

    def test_paths_are_spelled_from_the_plugin_root(self, config: Path) -> None:
        computed = [
            f"{path.relative_to(PLUGINS_DIR)}: {line.strip()}"
            for path, lines in _reached_scripts(config).items()
            for line in lines
            if COMPUTED_ROOT.search(line)
        ]
        assert computed == [], 'write "${CLAUDE_PLUGIN_ROOT}/scripts/<file>" instead'

    def test_programs_live_in_plugin_files(self, config: Path) -> None:
        inline = [
            f"{path.relative_to(PLUGINS_DIR)}: {line.strip()[:100]}"
            for path, lines in _reached_scripts(config).items()
            for line in lines
            if _inline_program(line)
        ]
        assert inline == [], 'move each program to a file run as -f "${CLAUDE_PLUGIN_ROOT}/…"'
