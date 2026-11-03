from pathlib import Path

import pytest

from tests.eval_tools.local_graders import Outcome, grade, hook_line, load_cases, scaffold

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/mz-dev-pipe"
HOOK = PLUGIN / "scripts/detect-tooling.sh"
CASES = load_cases(PLUGIN / "evals")
TOOLING_CASES = sorted(name for name in CASES if name.startswith("tooling-"))


class TestToolingCaseFixtures:
    def test_tooling_cases_exist(self) -> None:
        assert TOOLING_CASES, "no tooling-* cases in the mz-dev-pipe evals"

    @pytest.mark.parametrize("name", TOOLING_CASES)
    def test_file_and_trace_graders_pass_on_the_hook_alone(self, name: str, tmp_path: Path) -> None:
        workspace = scaffold(CASES[name], tmp_path)
        output = workspace.run_hook(HOOK, {"source": "startup"}, CLAUDE_PLUGIN_ROOT=str(PLUGIN))

        verdicts = grade(CASES[name].graders, Outcome(workspace.cwd, (hook_line(output),)))

        failing = [str(verdict) for verdict in verdicts if not verdict.passed]
        assert verdicts, f"{name} has no file or trace grader for a precheck to apply"
        detail = "\n".join(failing)
        assert not failing, f"{name}: the fixture and hook fail these graders:\n{detail}"
