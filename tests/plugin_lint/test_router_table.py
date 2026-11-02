import json
import re

from .conftest import PLUGINS_DIR, REPO_ROOT, DocSet, assert_no_violations

ROUTER = PLUGINS_DIR / "mz-base/skills/using-mozg-pipelines/SKILL.md"
# The last two cells of a routing row: the skill, whose first word is its name, and the plugin.
ROUTE_ROW = re.compile(
    r"^\|.*\|\s*`?(?P<skill>[a-z0-9-]+)`?[^|]*\|\s*(?P<plugin>mz-[a-z-]+)\s*\|\s*$", re.M
)


def _routes() -> set[tuple[str, str]]:
    routes = {(m["plugin"], m["skill"]) for m in ROUTE_ROW.finditer(ROUTER.read_text("utf-8"))}
    assert routes, f"{ROUTER.name} has no routing rows"
    return routes


def _marketplace_plugins() -> frozenset[str]:
    manifest = json.loads((REPO_ROOT / ".claude-plugin/marketplace.json").read_text("utf-8"))
    return frozenset(entry["name"] for entry in manifest["plugins"])


def _routable(frontmatter: dict[str, object]) -> bool:
    # A skill the user can't call, or the model can't invoke, is never a routing answer.
    return (
        frontmatter.get("user-invocable") is not False
        and frontmatter.get("disable-model-invocation") is not True
    )


class TestRouterTable:
    def test_every_routable_skill_has_a_row(self, skills: DocSet) -> None:
        routes = _routes()
        plugins = _marketplace_plugins()
        missing = [
            f"{parsed.doc.relative}: no row for {parsed.doc.plugin} {parsed.frontmatter['name']}"
            for parsed in skills.parsed
            if parsed.doc.plugin in plugins
            and _routable(parsed.frontmatter)
            and (parsed.doc.plugin, parsed.frontmatter["name"]) not in routes
        ]
        assert_no_violations(missing)

    def test_every_row_names_a_shipped_skill(self, skills: DocSet) -> None:
        shipped = {(parsed.doc.plugin, parsed.frontmatter["name"]) for parsed in skills.parsed}
        stale = [f"{plugin} {skill}" for plugin, skill in sorted(_routes() - shipped)]
        assert_no_violations(stale)
