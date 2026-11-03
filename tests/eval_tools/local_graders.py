"""Acts out an eval case locally, fixture and hooks included, and applies its graders to the result.
Prechecks use it to catch a broken fixture or grader pattern before a paid eval run."""

import json
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tests.e2e.smoke_common import plugin_free_env

type Grader = Mapping[str, Any]

BASH = shutil.which("bash") or "/bin/bash"
REGEX_FLAGS = {"i": re.I, "m": re.M, "s": re.S}
COMMAND_TIMEOUT_S = 60


class PrecheckError(RuntimeError):
    """A fixture or hook that failed, or a grader shape with no local rule."""


@dataclass(frozen=True)
class EvalCase:
    directory: Path
    spec: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.spec["name"])

    @property
    def tags(self) -> frozenset[str]:
        return frozenset(self.spec.get("tags") or ())

    @property
    def graders(self) -> list[Grader]:
        return list(self.spec.get("graders") or ())

    @property
    def prompt(self) -> str:
        return str(self.spec["execution"]["prompt"])

    @property
    def fixture(self) -> Path | None:
        script = (self.spec.get("context") or {}).get("scaffold_script")
        return self.directory / script if script else None


def load_cases(evals: Path) -> dict[str, EvalCase]:
    """Every case under `evals`, keyed by the name in its case.yaml."""
    if not evals.is_dir():
        raise PrecheckError(f"{evals} is not an evals directory")
    cases = [
        EvalCase(path.parent, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(evals.glob("*/case.yaml"))
    ]
    return {case.name: case for case in cases}


@dataclass(frozen=True)
class ToolCall:
    name: str
    input: dict[str, Any]

    def input_json(self) -> str:
        return json.dumps(self.input, separators=(",", ":"), ensure_ascii=False)

    def trace_line(self) -> str:
        event = {"type": "tool_use", "name": self.name, "input": self.input}
        return json.dumps(event, separators=(",", ":"), ensure_ascii=False)


def hook_line(output: str, hook_event: str | None = None) -> str:
    """One hook_response event, written the way the eval's stream-json trace writes it."""
    event = {"type": "system", "subtype": "hook_response"}
    if hook_event is not None:
        event["hook_event"] = hook_event
    event["output"] = output
    return json.dumps(event, separators=(",", ":"))


@dataclass(frozen=True)
class Workspace:
    home: Path
    cwd: Path
    env: dict[str, str]

    def run(self, command: Sequence[str], stdin: str = "", **extra_env: str) -> str:
        """Run `command` in the cwd with the project dir set, as a hook or a Bash call would be."""
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(self.cwd), **extra_env}
        try:
            result = subprocess.run(
                list(command),
                input=stdin,
                cwd=self.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise PrecheckError(f"{command[0]} timed out after {COMMAND_TIMEOUT_S}s") from error
        if result.returncode != 0:
            name = Path(command[1] if command[0] == BASH else command[0]).name
            raise PrecheckError(f"{name} exited {result.returncode}: {result.stderr.strip()}")
        return result.stdout

    def run_hook(self, script: Path, payload: Mapping[str, object], **extra_env: str) -> str:
        return self.run([BASH, str(script)], json.dumps(payload), **extra_env)


def scaffold(case: EvalCase, root: Path) -> Workspace:
    """Lay out the eval sandbox under `root` (a git-repo HOME around the cwd), run the fixture."""
    if case.fixture is None:
        raise PrecheckError(f"{case.name} has no scaffold_script")
    home = root / "home"
    cwd = home / "cwd"
    cwd.mkdir(parents=True)
    # The eval sandbox carries none of the caller's plugin settings, and its HOME is a git repo.
    workspace = Workspace(home, cwd, plugin_free_env({"HOME": str(home)}))
    workspace.run(["git", "init", "-q", str(home)])
    workspace.run([BASH, str(case.fixture)])
    return workspace


@dataclass(frozen=True)
class Outcome:
    """What one acted-out run leaves for the graders."""

    workspace: Path
    hook_lines: tuple[str, ...] = ()
    # None means the run acted out no tool use or reply, so graders on those are skipped.
    tool_calls: tuple[ToolCall, ...] | None = None
    reply: str | None = None

    @property
    def trace(self) -> str:
        calls = (call.trace_line() for call in self.tool_calls or ())
        return "\n".join([*self.hook_lines, *calls])


@dataclass(frozen=True)
class Verdict:
    grader: str
    passed: bool
    hits: int
    note: str = ""

    def __str__(self) -> str:
        note = f" ({self.note})" if self.note else ""
        return f"{'ok  ' if self.passed else 'FAIL'} {self.grader} hits={self.hits}{note}"


def grade(graders: Sequence[Grader], outcome: Outcome) -> list[Verdict]:
    """Verdicts, in order, for every grader `outcome` can answer."""
    verdicts = []
    for grader in graders:
        if "name" not in grader or "type" not in grader:
            raise PrecheckError(f"grader without a name or type: {dict(grader)}")
        if (verdict := _verdict(grader, outcome)) is not None:
            verdicts.append(verdict)
    return verdicts


def _verdict(grader: Grader, outcome: Outcome) -> Verdict | None:
    kind = grader["type"]
    if kind == "tool_used":
        return None if outcome.tool_calls is None else _tool_verdict(grader, outcome.tool_calls)
    if kind != "regex":
        raise PrecheckError(f"{grader['name']}: no local rule for grader type {kind!r}")
    target = grader.get("target", "last_message")
    note = ""
    if isinstance(target, Mapping):
        if target.get("source") != "file":
            raise PrecheckError(f"{grader['name']}: no local rule for target {dict(target)}")
        path = outcome.workspace / str(target["path"])
        # The eval grades a missing file as empty text, so a not_contains grader passes on it.
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        note = "" if path.is_file() else "file missing"
    elif target == "trace":
        text = outcome.trace
    elif target == "last_message":
        if outcome.reply is None:
            return None
        text = outcome.reply
    else:
        raise PrecheckError(f"{grader['name']}: no local rule for target {target!r}")
    hits = len(re.findall(str(grader["pattern"]), text, regex_flags(grader)))
    return Verdict(str(grader["name"]), _match_passes(grader, hits), hits, note)


def _tool_verdict(grader: Grader, calls: Sequence[ToolCall]) -> Verdict:
    input_match = grader.get("input_match")
    pattern = re.compile(str(input_match)) if input_match is not None else None
    hits = sum(
        1
        for call in calls
        if call.name == grader["tool"] and (pattern is None or pattern.search(call.input_json()))
    )
    low, high = int(grader.get("min", 1)), grader.get("max")
    passed = low <= hits and (high is None or hits <= int(high))
    return Verdict(str(grader["name"]), passed, hits)


def regex_flags(grader: Grader) -> re.RegexFlag:
    flags = re.RegexFlag(0)
    for letter in str(grader.get("flags", "")):
        if letter not in REGEX_FLAGS:
            raise PrecheckError(f"{grader['name']}: no local rule for regex flag {letter!r}")
        flags |= REGEX_FLAGS[letter]
    return flags


def _match_passes(grader: Grader, hits: int) -> bool:
    match = str(grader.get("match", "contains"))
    if match == "contains":
        return hits > 0
    if match == "not_contains":
        return hits == 0
    count = match.removeprefix("count:")
    if count != match and count.isdigit():
        return hits == int(count)
    raise PrecheckError(f"{grader['name']}: no local rule for match {match!r}")
