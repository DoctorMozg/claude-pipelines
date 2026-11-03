"""Stdio MCP server for gate_smoke: answers permission prompts, AskUserQuestion from a script.
Under `claude -p`, Claude Code offers AskUserQuestion only with a permission host like this."""

import json
import os
import sys
from pathlib import Path
from typing import Any

TOOL_NAME = "answer"
ASK_TOOL = "AskUserQuestion"
METHOD_NOT_FOUND = -32601


class GateHost:
    """Answers each AskUserQuestion with the next scripted answer; approves every other prompt."""

    def __init__(self, answers: list[str], log_path: Path | None) -> None:
        self.answers = list(answers)
        self.log_path = log_path

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        tool = request.get("tool_name")
        tool_input = request.get("input") or {}
        decision: dict[str, Any]
        if tool != ASK_TOOL:
            # An attending user approves these too; gate_smoke lists them as friction, not failures.
            decision = {"behavior": "allow", "updatedInput": tool_input}
            answer = None
        elif not self.answers:
            # Mirrors a user who never answers: the skill must stop, never assume approval.
            decision = {"behavior": "deny", "message": "Nobody answered this question."}
            answer = None
        else:
            answer = self.answers.pop(0)
            questions = tool_input.get("questions") or []
            answers = {question.get("question", ""): answer for question in questions}
            decision = {"behavior": "allow", "updatedInput": {**tool_input, "answers": answers}}
        self.record(
            {"tool": tool, "input": tool_input, "answer": answer, "behavior": decision["behavior"]}
        )
        return decision

    def record(self, entry: dict[str, Any]) -> None:
        if self.log_path is not None:
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry) + "\n")

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """The JSON-RPC response to one message; None for notifications."""
        msg_id = message.get("id")
        if msg_id is None:
            return None
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": params.get("protocolVersion"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "gate-host", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": [TOOL_SPEC]}
        elif method == "tools/call" and params.get("name") == TOOL_NAME:
            decision = self.decide(params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(decision)}]}
        else:
            error = {"code": METHOD_NOT_FOUND, "message": f"unsupported method {method}"}
            return {"jsonrpc": "2.0", "id": msg_id, "error": error}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}


TOOL_SPEC = {
    "name": TOOL_NAME,
    "description": "Answers Claude Code permission prompts for the gate smoke test.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "input": {"type": "object"},
            "tool_use_id": {"type": "string"},
        },
        "required": ["tool_name", "input"],
    },
}


def load_answers(raw: str) -> list[str]:
    answers = json.loads(raw)
    if not isinstance(answers, list) or not all(isinstance(a, str) for a in answers):
        raise ValueError(f"GATE_ANSWERS must be a JSON list of strings, got {raw!r}")
    return answers


def main() -> int:
    try:
        answers = load_answers(os.environ.get("GATE_ANSWERS", "[]"))
    except ValueError as error:
        print(f"gate_host: {error}", file=sys.stderr)
        return 2
    log_path = os.environ.get("GATE_HOST_LOG")
    host = GateHost(answers, Path(log_path) if log_path else None)
    for line in sys.stdin:
        response = host.handle(json.loads(line))
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
