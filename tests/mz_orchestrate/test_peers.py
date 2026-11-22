import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

PEERS = Path(__file__).resolve().parents[2] / "plugins" / "mz-orchestrate" / "scripts" / "peers.sh"
BASH = shutil.which("bash") or "/bin/bash"
REVIEW_ROLE = json.dumps(
    {
        "kinds": ["review"],
        "repos": "any",
        "paths": "any",
        "skills": "any",
        "note": "only for review",
    }
)

type Run = Callable[..., subprocess.CompletedProcess[str]]


class Peer(TypedDict):
    name: str
    ref: str
    address: str | None
    status: str
    role: dict[str, object]
    hello: dict[str, object] | None
    current_unit: str | None


class Registry(TypedDict):
    orchestrator: dict[str, str]
    peers: list[Peer]


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return tmp_path / ".mz" / "orchestrate" / "peers.json"


@pytest.fixture
def run(registry: Path) -> Run:
    def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [BASH, str(PEERS), str(registry), *args], capture_output=True, text=True, check=False
        )
        if check:
            assert result.returncode == 0, result.stderr
        return result

    return _run


@pytest.fixture
def attached(run: Run) -> Run:
    run("init", "orch-main", "078bfa")
    run("add", "ui-peer", "937dd8", REVIEW_ROLE)
    return run


def load(registry: Path) -> Registry:
    data: Registry = json.loads(registry.read_text())
    return data


def peer(registry: Path, name: str) -> Peer:
    return next(p for p in load(registry)["peers"] if p["name"] == name)


class TestRegistryLifecycle:
    def test_init_creates_the_registry_and_records_self(self, run: Run, registry: Path) -> None:
        run("init", "orch-main", "078bfa")

        data = load(registry)
        assert data["peers"] == []
        assert data["orchestrator"]["name"] == "orch-main"
        assert data["orchestrator"]["ref"] == "078bfa"

    def test_init_again_keeps_peers_and_updates_self(self, attached: Run, registry: Path) -> None:
        attached("init", "orch-main", "aaaaaa")

        assert load(registry)["orchestrator"]["ref"] == "aaaaaa"
        assert peer(registry, "ui-peer")["status"] == "pending"

    def test_add_starts_pending_with_the_role(self, attached: Run, registry: Path) -> None:
        added = peer(registry, "ui-peer")

        assert added["status"] == "pending"
        assert added["role"]["kinds"] == ["review"]
        assert added["address"] is None

    def test_add_twice_replaces_the_entry(self, attached: Run, registry: Path) -> None:
        attached("add", "ui-peer", "111111", json.dumps({"kinds": "any", "note": "any unit"}))

        peers = load(registry)["peers"]
        assert len(peers) == 1
        assert peers[0]["ref"] == "111111"

    def test_hello_attaches_and_pins_the_address(self, attached: Run, registry: Path) -> None:
        address = "uds:/run/user/1000/cc-socks/42.sock"
        attached("hello", "ui-peer", address, json.dumps({"cwd": "/repo", "worker-skill": "yes"}))

        hello = peer(registry, "ui-peer")
        assert hello["status"] == "attached"
        assert hello["address"] == address
        assert hello["hello"] == {"cwd": "/repo", "worker-skill": "yes"}

    def test_role_changes_only_the_role(self, attached: Run, registry: Path) -> None:
        attached("hello", "ui-peer", "uds:/x.sock", "{}")
        attached("role", "ui-peer", json.dumps({"kinds": ["change"], "note": "only UI"}))

        changed = peer(registry, "ui-peer")
        assert changed["role"]["note"] == "only UI"
        assert changed["status"] == "attached"
        assert changed["address"] == "uds:/x.sock"

    def test_remove_drops_the_peer(self, attached: Run, registry: Path) -> None:
        attached("remove", "ui-peer")

        assert load(registry)["peers"] == []

    def test_unit_records_and_clears_the_running_unit(self, attached: Run, registry: Path) -> None:
        attached("unit", "ui-peer", "t/WU-1")
        assert peer(registry, "ui-peer")["current_unit"] == "t/WU-1"

        attached("unit", "ui-peer", "none")
        assert peer(registry, "ui-peer")["current_unit"] is None

    def test_list_prints_one_tab_separated_row_per_peer(self, attached: Run) -> None:
        out = attached("list").stdout

        assert out == "ui-peer\t937dd8\tpending\tonly for review\t-\n"


class TestRegistryRejectsBadInput:
    def test_commands_before_init_fail(self, run: Run) -> None:
        result = run("list", check=False)

        assert result.returncode == 1
        assert "run init first" in result.stderr

    def test_unknown_peer_fails_with_its_name(self, attached: Run) -> None:
        result = attached("status", "ghost", "attached", check=False)

        assert result.returncode == 1
        assert "ghost" in result.stderr

    @pytest.mark.parametrize("role", ["not json", "[1, 2]", '"text"'])
    def test_role_must_be_a_json_object(self, attached: Run, role: str) -> None:
        result = attached("add", "other", "222222", role, check=False)

        assert result.returncode == 2
        assert "role-json must be a JSON object" in result.stderr

    def test_unknown_status_is_refused(self, attached: Run, registry: Path) -> None:
        result = attached("status", "ui-peer", "busy", check=False)

        assert result.returncode == 2
        assert peer(registry, "ui-peer")["status"] == "pending"

    def test_failed_update_leaves_the_registry_intact(self, attached: Run, registry: Path) -> None:
        before = registry.read_text()
        attached("hello", "ui-peer", "uds:/x.sock", "{broken", check=False)

        assert registry.read_text() == before
        assert list(registry.parent.glob("peers.json.*")) == []
