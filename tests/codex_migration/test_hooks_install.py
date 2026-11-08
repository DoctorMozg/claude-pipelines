import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from mozg_pipelines.hooks_install import HookConflictError, HookInstaller, HookInstallError


@pytest.fixture
def package(tmp_path: Path) -> Path:
    root = tmp_path / "rendered"
    (root / "hooks").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "plugin.json").write_text('{"name":"sample","version":"1.0.0"}')
    (root / "scripts/hook.sh").write_text(
        '#!/bin/sh\nprintf "%s\\n" "$PLUGIN_ROOT" "$PLUGIN_DATA" '
        '"$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_DATA" "$MZ_MEMORY_COMPRESS"\n'
        'cat\nprintf "hook stderr" >&2\nexit 7\n'
    )
    (root / "scripts/hook.sh").chmod(0o755)
    (root / "hooks/hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "startup",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": '"${PLUGIN_ROOT}"/scripts/hook.sh',
                                    "timeout": 10,
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )
    return root


@pytest.fixture
def installer(tmp_path: Path) -> HookInstaller:
    return HookInstaller(tmp_path / "home", "codex-cli 0.165.0")


@pytest.fixture
def fake_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    binary = tmp_path / "bin/codex"
    binary.parent.mkdir()
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])

    def set_version(version: str) -> None:
        binary.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(version) + "\n")
        binary.chmod(0o755)

    set_version("codex-cli 0.165.0")
    return set_version


def _config(installer: HookInstaller) -> dict[str, object]:
    value: dict[str, object] = json.loads((installer.codex_home / "hooks.json").read_text())
    return value


def _command(installer: HookInstaller) -> str:
    config = _config(installer)
    hooks = config["hooks"]
    assert isinstance(hooks, dict)
    groups = hooks["SessionStart"]
    assert isinstance(groups, list)
    command: str = groups[-1]["hooks"][0]["command"]
    return command


def test_install_preserves_user_hooks_and_is_idempotent(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.codex_home.mkdir()
    user_group = {"hooks": [{"type": "command", "command": "echo user"}]}
    stop_groups = [{"hooks": [{"type": "command", "command": "echo stop"}]}]
    original = {"description": "mine", "hooks": {"SessionStart": [user_group], "Stop": stop_groups}}
    (installer.codex_home / "hooks.json").write_text(json.dumps(original))
    result = installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert result.mode == "bridge"
    assert result.changed
    assert result.review_required
    assert not result.memory_compression_enabled
    config = _config(installer)
    assert config["description"] == "mine"
    hooks = config["hooks"]
    assert isinstance(hooks, dict)
    assert hooks["Stop"] == stop_groups
    assert hooks["SessionStart"][0] == user_group
    assert "dangerously" not in _command(installer)
    before = result.hooks_path.read_bytes()
    repeated = installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert not repeated.changed
    assert not repeated.review_required
    assert result.hooks_path.read_bytes() == before
    assert installer.status()["sample"]["mode"] == "bridge"


def test_update_changes_registration_and_uninstall_preserves_data(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    old_command = _command(installer)
    (package / "scripts/hook.sh").write_text("#!/bin/sh\necho updated\n")
    updated = installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert updated.changed
    assert updated.review_required
    assert _command(installer) != old_command
    data = installer.codex_home / "mozg-hooks/data/sample/memory.txt"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text("keep")
    assert installer.uninstall("sample")
    assert not installer.uninstall("sample")
    assert installer.status() == {}
    assert data.read_text() == "keep"
    assert _config(installer) == {"hooks": {}}


def test_native_transition_removes_bridge_without_touching_other_groups(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    result = installer.install(package, native_hooks=True, probed_version="codex-cli 0.165.0")
    assert result.mode == "native"
    assert result.changed
    assert not result.review_required
    assert _config(installer) == {"hooks": {}}
    assert installer.status()["sample"]["mode"] == "native"


@pytest.mark.parametrize("action", ["update", "uninstall", "native"])
def test_user_edited_managed_group_conflicts_without_writes(
    installer: HookInstaller,
    package: Path,
    action: str,
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    config = _config(installer)
    hooks = config["hooks"]
    assert isinstance(hooks, dict)
    hooks["SessionStart"][0]["matcher"] = "user-edited"
    config_path = installer.codex_home / "hooks.json"
    config_path.write_text(json.dumps(config))
    before = config_path.read_bytes()
    if action == "uninstall":
        with pytest.raises(HookConflictError, match=r"edited|changed"):
            installer.uninstall("sample")
    else:
        with pytest.raises(HookConflictError, match=r"edited|changed"):
            installer.install(
                package,
                native_hooks=action == "native",
                probed_version="codex-cli 0.165.0",
            )
    assert config_path.read_bytes() == before
    assert installer.status()["sample"]["mode"] == "bridge"


@pytest.mark.parametrize(("native", "version"), [(None, "codex-cli 0.165.0"), (False, "other")])
def test_install_requires_runtime_probe(
    installer: HookInstaller,
    package: Path,
    native: bool | None,
    version: str,
) -> None:
    with pytest.raises(HookInstallError, match=r"probe|version"):
        installer.install(package, native_hooks=native, probed_version=version)
    assert not installer.codex_home.exists()


def test_invalid_user_json_and_unsupported_handlers_are_not_overwritten(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.codex_home.mkdir()
    config = installer.codex_home / "hooks.json"
    config.write_text("{broken")
    with pytest.raises(HookInstallError, match="JSON"):
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert config.read_text() == "{broken"
    config.unlink()
    (package / "hooks/hooks.json").write_text(
        '{"hooks":{"Stop":[{"hooks":[{"type":"prompt","prompt":"decide"}]}]}}'
    )
    with pytest.raises(HookInstallError, match="command"):
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert not config.exists()


def test_dispatch_is_standalone_and_passes_environment_and_streams(
    installer: HookInstaller,
    package: Path,
    fake_codex: Callable[[str], None],
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    command = _command(installer)
    shutil.rmtree(package)
    process = subprocess.run(
        command, shell=True, input="private payload", capture_output=True, text=True, check=False
    )
    assert process.returncode == 7
    root, data, compat_root, compat_data, compress, payload = process.stdout.splitlines()
    assert root == compat_root
    assert Path(root).is_dir()
    assert data == compat_data
    assert Path(data).is_dir()
    assert compress == "0"
    assert payload == "private payload"
    assert process.stderr == "hook stderr"
    fake_codex("codex-cli upgraded")
    guarded = subprocess.run(
        command, shell=True, input="secret", capture_output=True, text=True, check=False
    )
    assert guarded.returncode == 0
    assert not guarded.stdout
    assert "doctor" in guarded.stderr
    assert "secret" not in guarded.stderr


def test_failed_registry_write_rolls_back_registration(
    installer: HookInstaller,
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mozg_pipelines.hooks_install as module

    installer.codex_home.mkdir()
    hooks = installer.codex_home / "hooks.json"
    hooks.write_text('{"description":"preserve original bytes"}')
    before = hooks.read_bytes()
    original = module._atomic_write

    def fail_registry(path: Path, content: bytes) -> None:
        if path.name == "registry.json":
            raise OSError("disk full")
        original(path, content)

    monkeypatch.setattr(module, "_atomic_write", fail_registry)
    with pytest.raises(HookInstallError, match="disk full"):
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert hooks.read_bytes() == before
    assert installer.status() == {}


def test_equivalent_unowned_groups_are_not_duplicated_or_removed(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    before = installer.hooks_path.read_bytes()
    installer.registry_path.write_text("{}")
    with pytest.raises(HookConflictError, match="without managed ownership"):
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert installer.hooks_path.read_bytes() == before
    assert not installer.uninstall("sample")
    assert installer.hooks_path.read_bytes() == before


def test_duplicated_owned_group_is_not_ambiguously_removed(
    installer: HookInstaller,
    package: Path,
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    config = _config(installer)
    hooks = config["hooks"]
    assert isinstance(hooks, dict)
    hooks["SessionStart"].append(hooks["SessionStart"][0])
    installer.hooks_path.write_text(json.dumps(config))
    before = installer.hooks_path.read_bytes()
    with pytest.raises(HookConflictError, match="changed"):
        installer.uninstall("sample")
    assert installer.hooks_path.read_bytes() == before


def test_stale_command_skips_after_update_and_uninstall(
    installer: HookInstaller,
    package: Path,
    fake_codex: Callable[[str], None],
) -> None:
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    old = _command(installer)
    (package / "scripts/hook.sh").write_text("#!/bin/sh\necho new\n")
    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    current = _command(installer)
    stale = subprocess.run(old, shell=True, capture_output=True, text=True, check=False)
    assert stale.returncode == 0
    assert not stale.stdout
    assert "doctor" in stale.stderr
    installer.uninstall("sample")
    removed = subprocess.run(current, shell=True, capture_output=True, text=True, check=False)
    assert removed.returncode == 0
    assert not removed.stdout


def test_cli_doctor_and_unknown_uninstall(
    installer: HookInstaller,
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mozg_pipelines import codex_hooks

    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    monkeypatch.setattr(codex_hooks, "codex_version", lambda: "codex-cli 0.165.0")
    args = ["--codex-home", str(installer.codex_home)]
    assert codex_hooks.main([*args, "doctor"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["registrations"]["sample"]["mode"] == "bridge"
    assert codex_hooks.main([*args, "uninstall", "missing"]) == 0
    assert json.loads(capsys.readouterr().out) == {"plugin": "missing", "removed": False}


def test_cli_renders_canonical_hooks_without_changing_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mozg_pipelines.codex_hooks import main

    repository = Path(__file__).resolve().parents[2]
    source = repository / "plugins/mz-memory/hooks/hooks.json"
    before = source.read_bytes()
    output = tmp_path / "package"
    assert main(["render", "mz-memory", "--repo", str(repository), "--output", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["package"] == str(output)
    assert response["hooks"] == ["hooks/hooks.json"]
    assert (output / "scripts/memory-inject.sh").is_file()
    assert source.read_bytes() == before
    assert not list(output.rglob("case.yaml"))


def test_cli_rejects_unknown_plugin(tmp_path: Path) -> None:
    from mozg_pipelines.codex_hooks import main

    repository = Path(__file__).resolve().parents[2]
    with pytest.raises(SystemExit) as error:
        main(["render", "unknown", "--repo", str(repository), "--output", str(tmp_path / "out")])
    assert error.value.code == 2
    assert not (tmp_path / "out").exists()


def test_cli_unknown_probe_does_not_install(
    installer: HookInstaller,
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mozg_pipelines import codex_hooks
    from mozg_pipelines.hooks_probe import ProbeResult

    monkeypatch.setattr(codex_hooks, "codex_version", lambda: "codex-cli 0.165.0")

    def unknown(*, codex_home: Path, model: str) -> ProbeResult:
        return ProbeResult("codex-cli 0.165.0", None, (), ("control failed",))

    monkeypatch.setattr(codex_hooks, "probe_hooks", unknown)
    assert (
        codex_hooks.main(
            [
                "--codex-home",
                str(installer.codex_home),
                "install",
                str(package),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["installed"] is False
    assert not installer.codex_home.exists()


@pytest.mark.parametrize("raw", ['{"hooks":{},"hooks":{}}', '{"custom":NaN}', "[]"])
def test_ambiguous_or_nonstandard_json_is_not_rewritten(
    installer: HookInstaller,
    package: Path,
    raw: str,
) -> None:
    installer.codex_home.mkdir()
    installer.hooks_path.write_text(raw)
    with pytest.raises(HookInstallError, match="JSON"):
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert installer.hooks_path.read_text() == raw
    assert not installer.registry_path.exists()


@pytest.mark.parametrize("existing_bridge", [False, True])
def test_native_memory_requires_maintenance_port_without_changing_state(
    installer: HookInstaller,
    package: Path,
    existing_bridge: bool,
) -> None:
    (package / "plugin.json").write_text('{"name":"mz-memory","version":"1.0.0"}')
    if existing_bridge:
        installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    before = installer.hooks_path.read_bytes() if existing_bridge else None
    with pytest.raises(HookInstallError, match="maintenance port"):
        installer.install(package, native_hooks=True, probed_version="codex-cli 0.165.0")
    if before is None:
        assert not installer.codex_home.exists()
    else:
        assert installer.hooks_path.read_bytes() == before
        assert installer.status()["mz-memory"]["mode"] == "bridge"


def test_cli_doctor_reports_incompatible_runtime(
    installer: HookInstaller,
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mozg_pipelines import codex_hooks

    installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    monkeypatch.setattr(codex_hooks, "codex_version", lambda: "codex-cli 0.166.0")
    before = installer.hooks_path.read_bytes()
    assert codex_hooks.main(["--codex-home", str(installer.codex_home), "doctor"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["registrations"]["sample"]["runtime_compatible"] is False
    assert installer.hooks_path.read_bytes() == before


def test_package_file_boundaries_change_trust_digest(
    installer: HookInstaller,
    package: Path,
) -> None:
    prefix = b"#!/bin/sh\necho before\n"
    metadata = (json.dumps(["scripts/z.sh", 0o644], indent=2) + "\n").encode()
    payload = b"echo after\n"
    script = package / "scripts/hook.sh"
    script.write_bytes(prefix + metadata + payload)
    first = installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    command = _command(installer)
    script.write_bytes(prefix)
    extra = package / "scripts/z.sh"
    extra.write_bytes(payload)
    extra.chmod(0o644)
    updated = installer.install(package, native_hooks=False, probed_version="codex-cli 0.165.0")
    assert updated.changed
    assert updated.review_required
    assert updated.package_root != first.package_root
    assert _command(installer) != command
