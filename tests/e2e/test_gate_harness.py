"""Offline tests for the gate smoke harness: the scripted permission host and the journal reader."""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.gate_host import ASK_TOOL, METHOD_NOT_FOUND, TOOL_NAME, GateHost, load_answers
from tests.e2e.gate_smoke import JOURNAL, SCENARIOS, GateRun, gate_question
from tests.e2e.smoke_common import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_SCRIPT = REPO_ROOT / "tests" / "e2e" / "gate_host.py"

type HostFactory = Callable[..., GateHost]


def ask(*questions: str) -> dict[str, Any]:
    return {
        "tool_name": ASK_TOOL,
        "input": {"questions": [{"question": q, "options": []} for q in questions]},
    }


def call(msg_id: int, arguments: dict[str, Any], name: str = TOOL_NAME) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def decision_of(response: dict[str, Any] | None) -> dict[str, Any]:
    assert response is not None
    decision: dict[str, Any] = json.loads(response["result"]["content"][0]["text"])
    return decision


@pytest.fixture
def host_log(tmp_path: Path) -> Path:
    return tmp_path / "host.jsonl"


@pytest.fixture
def make_host(host_log: Path) -> HostFactory:
    return lambda *answers: GateHost(list(answers), host_log)


class TestDecisions:
    def test_answers_are_used_in_order(self, make_host: HostFactory) -> None:
        host = make_host("Change it", "Approve")
        first = host.decide(ask("Ready?"))
        second = host.decide(ask("Ready?"))
        assert first["updatedInput"]["answers"] == {"Ready?": "Change it"}
        assert second["updatedInput"]["answers"] == {"Ready?": "Approve"}

    def test_every_question_in_one_call_gets_the_answer(self, make_host: HostFactory) -> None:
        decision = make_host("Reject").decide(ask("First?", "Second?"))
        assert decision["behavior"] == "allow"
        assert decision["updatedInput"]["answers"] == {"First?": "Reject", "Second?": "Reject"}
        assert len(decision["updatedInput"]["questions"]) == 2

    def test_no_answer_left_is_a_denial(self, make_host: HostFactory) -> None:
        host = make_host("Approve")
        host.decide(ask("Ready?"))
        assert host.decide(ask("Ready?"))["behavior"] == "deny"

    def test_other_prompts_are_approved_without_using_an_answer(
        self, make_host: HostFactory
    ) -> None:
        host = make_host("Approve")
        bash = {"tool_name": "Bash", "input": {"command": "git status"}}
        assert host.decide(bash) == {"behavior": "allow", "updatedInput": bash["input"]}
        assert host.decide(ask("Ready?"))["updatedInput"]["answers"] == {"Ready?": "Approve"}

    def test_each_request_is_logged(self, make_host: HostFactory, host_log: Path) -> None:
        host = make_host("Approve")
        host.decide({"tool_name": "Write", "input": {}})
        host.decide(ask("Ready?"))
        host.decide(ask("Again?"))
        entries = [json.loads(line) for line in host_log.read_text().splitlines()]
        assert [(e["tool"], e["answer"], e["behavior"]) for e in entries] == [
            ("Write", None, "allow"),
            (ASK_TOOL, "Approve", "allow"),
            (ASK_TOOL, None, "deny"),
        ]


class TestProtocol:
    def test_initialize_echoes_the_protocol_version(self, make_host: HostFactory) -> None:
        response = make_host().handle(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            }
        )
        assert response is not None
        assert response["result"]["protocolVersion"] == "2025-11-25"
        assert "tools" in response["result"]["capabilities"]

    def test_tools_list_offers_the_answer_tool(self, make_host: HostFactory) -> None:
        response = make_host().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response is not None
        assert [tool["name"] for tool in response["result"]["tools"]] == [TOOL_NAME]

    def test_notifications_get_no_reply(self, make_host: HostFactory) -> None:
        assert make_host().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    @pytest.mark.parametrize(
        "message",
        [
            {"jsonrpc": "2.0", "id": 2, "method": "server/discover"},
            call(3, ask("Ready?"), name="other"),
        ],
        ids=["unknown-method", "unknown-tool"],
    )
    def test_unsupported_requests_get_method_not_found(
        self, make_host: HostFactory, message: dict[str, Any]
    ) -> None:
        response = make_host("Approve").handle(message)
        assert response is not None
        assert response["error"]["code"] == METHOD_NOT_FOUND

    def test_tool_call_returns_the_decision_as_text(self, make_host: HostFactory) -> None:
        assert (
            decision_of(make_host("Approve").handle(call(4, ask("Ready?"))))["behavior"] == "allow"
        )


class TestAnswerScript:
    @pytest.mark.parametrize("raw", ['"Approve"', "[1, 2]", "{}"])
    def test_rejects_anything_but_a_list_of_strings(self, raw: str) -> None:
        with pytest.raises(ValueError, match="JSON list of strings"):
            load_answers(raw)

    def test_rejects_broken_json(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            load_answers("not json")

    def test_accepts_an_empty_script(self) -> None:
        assert load_answers("[]") == []


class TestServerProcess:
    def run_server(
        self, answers: str, *messages: dict[str, Any]
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "GATE_ANSWERS": answers}
        env.pop("GATE_HOST_LOG", None)
        stdin = "".join(json.dumps(message) + "\n" for message in messages)
        return subprocess.run(
            [sys.executable, "-I", str(HOST_SCRIPT)],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_answers_over_stdio(self) -> None:
        result = self.run_server(
            '["Reject"]',
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            call(1, ask("Proceed?")),
        )
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        assert result.returncode == 0
        assert [reply["id"] for reply in replies] == [0, 1]
        assert decision_of(replies[1])["updatedInput"]["answers"] == {"Proceed?": "Reject"}

    def test_bad_answer_script_exits_2(self) -> None:
        result = self.run_server('"Approve"')
        assert result.returncode == 2
        assert "GATE_ANSWERS" in result.stderr


class TestJournalReader:
    SESSION = "11111111-2222-3333-4444-555555555555"

    def entry(self, session: str, response: str) -> str:
        return (
            f"### 2026-11-03T00:00:00Z · session {session} · AskUserQuestion\n\n"
            'questions (verbatim):\n[{"question":"Ready?"}]\n\n'
            f"response (verbatim):\n{response}\n"
        )

    def gate_run(self, tmp_path: Path, journal: str) -> GateRun:
        (tmp_path / JOURNAL).parent.mkdir(parents=True)
        (tmp_path / JOURNAL).write_text(journal, encoding="utf-8")
        return GateRun(Session("x", [], 0.0), tmp_path, self.SESSION, [])

    def test_reads_only_this_sessions_answers_in_order(self, tmp_path: Path) -> None:
        journal = "# Interaction Journal\n\n<!-- header -->\n\n" + "\n".join(
            [
                self.entry(self.SESSION, '{"answers":{"Ready?":"Change it"}}'),
                self.entry("other-session", '{"answers":{"Ready?":"Reject"}}'),
                self.entry(self.SESSION, '{"answers":{"Ready?":"Approve"}}'),
            ]
        )
        assert self.gate_run(tmp_path, journal).journal_answers() == ["Change it", "Approve"]

    def test_an_unparsable_response_is_reported_not_dropped(self, tmp_path: Path) -> None:
        answers = self.gate_run(
            tmp_path, "\n" + self.entry(self.SESSION, "plain text")
        ).journal_answers()
        assert answers == ["unparsed response: plain text"]

    def test_no_journal_means_no_answers(self, tmp_path: Path) -> None:
        assert GateRun(Session("x", [], 0.0), tmp_path, self.SESSION, []).journal_answers() == []


class TestScenarioContracts:
    @pytest.mark.parametrize("skill", sorted({s.skill for s in SCENARIOS}), ids=str)
    def test_each_gated_skill_still_names_its_gate_question(self, skill: Path) -> None:
        assert gate_question(REPO_ROOT / "plugins" / skill).endswith("ready for review.")

    def test_scenario_labels_are_unique(self) -> None:
        labels = [s.label for s in SCENARIOS]
        assert len(labels) == len(set(labels))
