import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-research-pipe"
SKILL = PLUGIN / "skills/combine/SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _banned_tokens() -> list[str]:
    check = re.search(r"Vague-task check\*\*.*?banned tokens? \(([^)]*)\)", _skill_text())
    assert check, "combine's vague-task check names no banned tokens"
    tokens = re.findall(r"`([^`]+)`", check.group(1))
    assert tokens, "the banned-token list is empty or unparsable"
    return tokens


def _min_task_tokens() -> int:
    bound = re.search(r"MIN_TASK_QUERY_TOKENS = (\d+)", _skill_text())
    assert bound, "MIN_TASK_QUERY_TOKENS is not defined"
    return int(bound.group(1))


def _fire_prompts() -> dict[str, str]:
    prompts: dict[str, str] = {}
    for case_file in sorted((REPO_ROOT / "evals/mz-research-pipe").glob("combine-*/case.yaml")):
        case = yaml.safe_load(case_file.read_text(encoding="utf-8"))
        if "fire" in case.get("tags", []):
            prompts[case_file.parent.name] = case["execution"]["prompt"]
    return prompts


FIRE_PROMPTS = _fire_prompts()


class TestVagueTaskCheck:
    def test_suite_has_fire_cases(self) -> None:
        assert FIRE_PROMPTS

    @pytest.mark.parametrize("case", sorted(FIRE_PROMPTS))
    def test_fire_prompt_has_enough_tokens(self, case: str) -> None:
        assert len(FIRE_PROMPTS[case].split()) >= _min_task_tokens()

    @pytest.mark.parametrize("case", sorted(FIRE_PROMPTS))
    def test_fire_prompt_has_no_banned_token(self, case: str) -> None:
        prompt = FIRE_PROMPTS[case]
        hits = [
            token
            for token in _banned_tokens()
            if re.search(rf"\b{re.escape(token)}\b", prompt, re.IGNORECASE)
        ]
        assert hits == []
