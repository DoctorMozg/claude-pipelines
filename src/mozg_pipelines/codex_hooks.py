"""Render and register converted hooks without changing their canonical definitions.

Examples (from the repository):
  PYTHONPATH=src python -m mozg_pipelines.codex_hooks render mz-memory --output /tmp/mz-memory
  PYTHONPATH=src python -m mozg_pipelines.codex_hooks --codex-home /tmp/codex doctor --live
  PYTHONPATH=src python -m mozg_pipelines.codex_hooks install /tmp/mz-memory
  PYTHONPATH=src python -m mozg_pipelines.codex_hooks uninstall mz-memory

Install performs an isolated model-backed capability probe. Installed hooks still
require the user's normal /hooks trust review. Live diagnostics trust only their
temporary probe definitions, never the user's installed hooks.
Converted mz-memory installations enable Codex curation; MZ_MEMORY_COMPRESS=0 opts out.
"""

import argparse
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

from mozg_pipelines.hooks_install import HookInstaller, HookInstallError
from mozg_pipelines.hooks_probe import codex_version, probe_hooks
from mozg_pipelines.inventory import (
    build_codex_package_spec,
    discover_packages,
    load_migration_plan,
)
from mozg_pipelines.rendering import render_codex_package

LOGGER = logging.getLogger(__name__)


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="Render one canonical package")
    render.add_argument("plugin")
    render.add_argument("--repo", type=Path, default=Path.cwd())
    render.add_argument("--output", type=Path, required=True)
    install = commands.add_parser("install", help="Register hooks from a rendered package")
    install.add_argument("package", type=Path)
    install.add_argument("--model", default="gpt-6.1-sol")
    uninstall = commands.add_parser("uninstall", help="Remove only owned hook registrations")
    uninstall.add_argument("plugin")
    doctor = commands.add_parser("doctor", help="Inspect registration and runtime compatibility")
    doctor.add_argument("--live", action="store_true", help="Run an isolated model-backed probe")
    doctor.add_argument("--model", default="gpt-6.1-sol")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    home = args.codex_home.expanduser().resolve()

    try:
        if args.command == "render":
            repository = args.repo.resolve()
            plan = load_migration_plan(repository / "data/codex_migration.toml")
            package = next(
                (
                    item
                    for item in discover_packages(plan, repository)
                    if item.plan.name == args.plugin
                ),
                None,
            )
            if package is None:
                parser.error(f"Unknown canonical plugin: {args.plugin}")
            rendered = render_codex_package(
                build_codex_package_spec(package, repository, args.output.resolve())
            )
            _emit({"package": rendered.package_root, "hooks": rendered.hook_paths})
            return 0

        version = codex_version() if args.command != "uninstall" else "unavailable"
        installer = HookInstaller(home, version)
        if args.command == "uninstall":
            _emit({"plugin": args.plugin, "removed": installer.uninstall(args.plugin)})
            return 0
        if args.command == "doctor":
            registrations = {
                name: {**info, "runtime_compatible": info["runtime_version"] == version}
                for name, info in installer.status().items()
            }
            compatible = all(info["runtime_compatible"] for info in registrations.values())
            result_data: dict[str, object] = {
                "runtime_version": version,
                "registrations": registrations,
            }
            if args.live:
                probe = probe_hooks(codex_home=home, model=args.model)
                result_data["probe"] = asdict(probe)
                _emit(result_data)
                return 0 if compatible and probe.native_hooks is not None else 1
            _emit(result_data)
            return 0 if compatible else 1

        package_root = args.package.resolve()
        manifest: object = json.loads((package_root / "plugin.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise HookInstallError("Rendered plugin manifest must contain a JSON object")
        probe = probe_hooks(codex_home=home, model=args.model)
        if probe.native_hooks is None:
            _emit({"installed": False, "probe": asdict(probe)})
            return 1
        result = installer.install(
            package_root,
            native_hooks=probe.native_hooks,
            probed_version=probe.runtime_version,
            enable_memory_maintenance=manifest.get("name") == "mz-memory",
        )
        _emit({"installation": asdict(result), "probe": asdict(probe)})
        if result.mode == "bridge":
            print("Open /hooks in Codex to review and trust the registered definitions.")
            if result.memory_compression_enabled:
                print("Memory compression and curation use Codex; MZ_MEMORY_COMPRESS=0 opts out.")
            elif result.name == "mz-memory":
                print("Memory compression and curation are disabled for this installation.")
        else:
            print(
                "Native hooks are available. Enable the converted package "
                "through Codex's plugin manager."
            )
        return 0
    except (HookInstallError, OSError, RuntimeError, ValueError) as error:
        LOGGER.error("Codex hook %s failed: %s", args.command, error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
