"""Install rendered command hooks without replacing user hook configuration."""

import copy
import fcntl
import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

logger = logging.getLogger(__name__)
HookGroups = dict[str, list[dict[str, JsonValue]]]
Mode = Literal["native", "bridge"]
_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
_PYTHON = str(Path(sys.executable).resolve())

# This must remain stdlib-only: installed hooks outlive the checkout and its virtualenv.
_DISPATCHER = """import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    state = Path(__file__).resolve().parent
    try:
        name, digest, key, policy = sys.argv[1:]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ValueError("invalid plugin name")
        record = json.loads((state / "registry.json").read_text())[name]
        if record["digest"] != digest or record["mode"] != "bridge":
            raise ValueError("registration changed")
        memory_enabled = record.get("memory_compression_enabled", False)
        expected_policy = "memory-codex-v1" if memory_enabled else "memory-disabled"
        if policy != expected_policy:
            raise ValueError("maintenance policy changed")
        version = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        if version != record["runtime_version"]:
            raise ValueError("Codex runtime version changed")
        root = state / "packages" / name / digest
        if str(root) != record["package_root"] or not root.is_dir():
            raise ValueError("installed package is missing")
        data = state / "data" / name
        env = dict(os.environ)
        env.update(PLUGIN_ROOT=str(root), PLUGIN_DATA=str(data),
                   CLAUDE_PLUGIN_ROOT=str(root), CLAUDE_PLUGIN_DATA=str(data))
        if memory_enabled:
            env["MZ_MEMORY_CURATOR_BACKEND"] = "codex"
            env["MZ_MEMORY_COMPRESS"] = "0" if env.get("MZ_MEMORY_COMPRESS") == "0" else "1"
        else:
            env["MZ_MEMORY_COMPRESS"] = "0"
        command = record["commands"][key]
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("mozg hooks skipped: run codex_hooks doctor and reinstall to validate hooks.",
              file=sys.stderr)
        return 0
    try:
        result = subprocess.run(command, shell=True, env=env, check=False)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except OSError:
        print("mozg hook could not start; run codex_hooks doctor.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""


class HookInstallError(RuntimeError):
    """The installer refused a change or could not commit it."""


class HookConflictError(HookInstallError):
    """Previously managed configuration was edited outside the installer."""


@dataclass(frozen=True)
class InstallResult:
    name: str
    mode: Mode
    changed: bool
    hooks_path: Path
    review_required: bool
    package_root: Path
    memory_compression_enabled: bool = False


class InstalledHookInfo(TypedDict):
    mode: Mode
    digest: str
    runtime_version: str
    package_root: str
    memory_compression_enabled: bool


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Mode
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_version: str
    package_root: str
    groups: HookGroups
    commands: dict[str, str]
    memory_compression_enabled: bool = False


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _read_object(path: Path) -> dict[str, JsonValue]:
    if path.is_symlink():
        raise HookInstallError(f"Refusing symlink configuration: {path}")
    try:
        value: JsonValue = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, ValueError) as exc:
        raise HookInstallError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HookInstallError(f"JSON must contain an object: {path}")
    return value


def _events(config: dict[str, JsonValue], *, command_only: bool = False) -> HookGroups:
    events = config.setdefault("hooks", {})
    if not isinstance(events, dict):
        raise HookInstallError("hooks must be an object of event groups")
    for event, groups in events.items():
        if not isinstance(groups, list):
            raise HookInstallError(f"Hook event {event} must contain a list")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise HookInstallError(f"Hook event {event} has an invalid group")
            handlers = group["hooks"]
            assert isinstance(handlers, list)
            for handler in handlers:
                if not isinstance(handler, dict):
                    raise HookInstallError(f"Hook event {event} has an invalid handler")
                if command_only and (
                    handler.get("type") != "command"
                    or not isinstance(handler.get("command"), str)
                    or not handler["command"]
                    or "commandWindows" in handler
                ):
                    raise HookInstallError("Bridge supports nonempty POSIX command hooks only")
    return cast(HookGroups, events)


def _atomic_write(path: Path, content: bytes) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _encode(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def _require_memory_backend(root: Path) -> None:
    try:
        supported = re.search(
            r"(?m)^curator_codex_call\s*\(\s*\)\s*\{",
            (root / "scripts/lib/curator.sh").read_text(encoding="utf-8"),
        )
    except OSError as exc:
        raise HookInstallError("Re-render mz-memory with the Codex curator backend") from exc
    if supported is None:
        raise HookInstallError("Re-render mz-memory with the supported Codex curator backend")


class HookInstaller:
    def __init__(self, codex_home: Path, runtime_version: str) -> None:
        if not runtime_version.strip():
            raise HookInstallError("A nonempty probed runtime version is required")
        self.codex_home = codex_home.expanduser().resolve()
        self.runtime_version = runtime_version.strip()
        self.hooks_path = self.codex_home / "hooks.json"
        self.state = self.codex_home / "mozg-hooks"
        self.registry_path = self.state / "registry.json"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.state.is_symlink() or self.hooks_path.is_symlink():
            raise HookInstallError("Refusing symlink hook state or configuration")
        lock = self.state / "install.lock"
        if lock.is_symlink():
            raise HookInstallError("Refusing symlink installation lock")
        with lock.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _registry(self) -> dict[str, _Record]:
        if not self.registry_path.exists():
            return {}
        try:
            records = _read_object(self.registry_path)
            if any(not _NAME.fullmatch(name) for name in records):
                raise HookInstallError("Invalid plugin name in hook registry")
            return {name: _Record.model_validate(value) for name, value in records.items()}
        except ValidationError as exc:
            raise HookInstallError(f"Invalid hook registry: {exc}") from exc

    def _config(self) -> dict[str, JsonValue]:
        config = _read_object(self.hooks_path) if self.hooks_path.exists() else {}
        _events(config)
        return config

    @staticmethod
    def _remove_owned(events: HookGroups, record: _Record | None) -> None:
        if record is None:
            return
        for event, groups in record.groups.items():
            current = events.get(event, [])
            for group in groups:
                if current.count(group) != 1:
                    raise HookConflictError(
                        f"Managed {event} hook was changed, edited or removed; resolve it manually"
                    )
                current.remove(group)
            if not current:
                events.pop(event, None)

    def _commit(self, config: dict[str, JsonValue], records: dict[str, _Record]) -> None:
        paths = (self.hooks_path, self.registry_path)
        originals = {path: path.read_bytes() if path.exists() else None for path in paths}
        updated: list[Path] = []
        try:
            contents = (_encode(config), _encode({k: v.model_dump() for k, v in records.items()}))
            for path, content in zip(paths, contents, strict=True):
                _atomic_write(path, content)
                updated.append(path)
        except OSError as exc:
            for path in reversed(updated):
                original = originals[path]
                if original is None:
                    path.unlink()
                else:
                    _atomic_write(path, original)
            logger.exception("Hook registration transaction failed")
            raise HookInstallError(f"Hook registration failed and was rolled back: {exc}") from exc

    def _digest(self, root: Path) -> str:
        digest = hashlib.sha256()
        digest.update(_DISPATCHER.encode())
        digest.update(self.runtime_version.encode())
        digest.update(_PYTHON.encode())
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise HookInstallError(f"Rendered package contains symlink: {path}")
            if path.is_file():
                digest.update(
                    _encode(
                        [
                            path.relative_to(root).as_posix(),
                            path.stat().st_mode & 0o777,
                            hashlib.sha256(path.read_bytes()).hexdigest(),
                        ]
                    )
                )
            elif not path.is_dir():
                raise HookInstallError(f"Rendered package contains a special file: {path}")
        return digest.hexdigest()

    def _snapshot(self, root: Path, name: str, digest: str) -> Path:
        destination = self.state / "packages" / name / digest
        if destination.exists():
            if self._digest(destination) != digest:
                raise HookConflictError(
                    "Installed package snapshot was changed; refusing overwrite"
                )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                dir=destination.parent, prefix=".install-"
            ) as temporary:
                staged = Path(temporary) / "package"
                shutil.copytree(root, staged)
                if self._digest(staged) != digest:
                    raise HookInstallError("Rendered package changed during installation; retry")
                staged.rename(destination)
        (self.state / "data" / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        return destination

    def _bridge(
        self, groups: HookGroups, name: str, digest: str, *, memory_enabled: bool
    ) -> tuple[HookGroups, dict[str, str]]:
        generated = copy.deepcopy(groups)
        commands: dict[str, str] = {}
        script_hash = hashlib.sha256(_DISPATCHER.encode()).hexdigest()
        dispatcher = self.state / f"dispatch-{script_hash}.py"
        if dispatcher.exists() and dispatcher.read_text() != _DISPATCHER:
            raise HookConflictError("Installed dispatcher was changed; refusing overwrite")
        if not dispatcher.exists():
            _atomic_write(dispatcher, _DISPATCHER.encode())
        for event, event_groups in generated.items():
            for group_index, group in enumerate(event_groups):
                handlers = cast(list[dict[str, JsonValue]], group["hooks"])
                for handler_index, handler in enumerate(handlers):
                    key = f"{event}:{group_index}:{handler_index}"
                    commands[key] = cast(str, handler["command"])
                    policy = "memory-codex-v1" if memory_enabled else "memory-disabled"
                    handler["command"] = shlex.join(
                        [_PYTHON, str(dispatcher), name, digest, key, policy]
                    )
        return generated, commands

    def install(
        self,
        package_root: Path,
        *,
        native_hooks: bool | None,
        probed_version: str,
        enable_memory_maintenance: bool = False,
    ) -> InstallResult:
        if not isinstance(enable_memory_maintenance, bool):
            raise HookInstallError("enable_memory_maintenance must be a boolean")
        if native_hooks is None or probed_version.strip() != self.runtime_version:
            raise HookInstallError(
                "A successful hook probe for this exact runtime version is required"
            )
        root = package_root.resolve()
        if root == self.state or self.state in root.parents or root in self.state.parents:
            raise HookInstallError("Rendered package must be outside the managed hook state")
        manifest = _read_object(root / "plugin.json")
        name = manifest.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise HookInstallError("Rendered plugin manifest has an invalid name")
        if native_hooks and name == "mz-memory":
            raise HookInstallError(
                "Native mz-memory maintenance port requires a native environment adapter; "
                "use the bridge until that adapter is available"
            )
        if enable_memory_maintenance:
            if name != "mz-memory":
                raise HookInstallError("Codex memory maintenance is supported only for mz-memory")
            _require_memory_backend(root)
        groups = _events(_read_object(root / "hooks/hooks.json"), command_only=True)
        digest = self._digest(root)
        mode: Mode = "native" if native_hooks else "bridge"
        try:
            with self._locked():
                config, records = self._config(), self._registry()
                events = _events(config)
                previous = records.get(name)
                self._remove_owned(events, previous)
                installed = self._snapshot(root, name, digest)
                if enable_memory_maintenance:
                    _require_memory_backend(installed)
                groups = _events(_read_object(installed / "hooks/hooks.json"), command_only=True)
                generated, commands = (
                    self._bridge(groups, name, digest, memory_enabled=enable_memory_maintenance)
                    if not native_hooks
                    else ({}, {})
                )
                record = _Record(
                    mode=mode,
                    digest=digest,
                    runtime_version=self.runtime_version,
                    package_root=str(installed),
                    groups=generated,
                    commands=commands,
                    memory_compression_enabled=enable_memory_maintenance,
                )
                if previous == record:
                    return InstallResult(
                        name,
                        mode,
                        False,
                        self.hooks_path,
                        False,
                        installed,
                        memory_compression_enabled=enable_memory_maintenance,
                    )
                for event, event_groups in generated.items():
                    if any(group in events.get(event, []) for group in event_groups):
                        raise HookConflictError(
                            f"Equivalent {event} hook already exists without managed ownership"
                        )
                    events.setdefault(event, []).extend(event_groups)
                records[name] = record
                self._commit(config, records)
                logger.info(
                    "Installed %s hooks for %s; Codex memory maintenance %s",
                    mode,
                    name,
                    "enabled" if enable_memory_maintenance else "disabled",
                )
                return InstallResult(
                    name,
                    mode,
                    True,
                    self.hooks_path,
                    bool(generated),
                    installed,
                    memory_compression_enabled=enable_memory_maintenance,
                )
        except OSError as exc:
            logger.exception("Hook installation failed for %s", name)
            raise HookInstallError(f"Cannot install hooks for {name}: {exc}") from exc

    def uninstall(self, name: str) -> bool:
        if not _NAME.fullmatch(name):
            raise HookInstallError("Invalid plugin name")
        if not self.registry_path.exists():
            return False
        with self._locked():
            config, records = self._config(), self._registry()
            record = records.get(name)
            if record is None:
                return False
            self._remove_owned(_events(config), record)
            del records[name]
            self._commit(config, records)
            logger.info("Unregistered hooks for %s; retained package snapshots and data", name)
            return True

    def status(self) -> dict[str, InstalledHookInfo]:
        return {
            name: InstalledHookInfo(
                mode=record.mode,
                digest=record.digest,
                runtime_version=record.runtime_version,
                package_root=record.package_root,
                memory_compression_enabled=record.memory_compression_enabled,
            )
            for name, record in self._registry().items()
        }
