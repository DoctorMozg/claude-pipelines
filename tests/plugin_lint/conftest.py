import re
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "plugins"
_FRONTMATTER = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys, which PyYAML silently resolves to the last one."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, object]:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class PluginDoc:
    path: Path
    plugin: str
    frontmatter_text: str | None
    body: str

    @property
    def relative(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class ParsedDoc:
    doc: PluginDoc
    frontmatter: dict[str, object]


@dataclass(frozen=True)
class DocSet:
    docs: tuple[PluginDoc, ...]
    parsed: tuple[ParsedDoc, ...]
    parse_errors: tuple[str, ...]


def parse_frontmatter(text: str) -> dict[str, object]:
    """Parse frontmatter strictly; raise YAMLError or TypeError unless it is a str-keyed mapping."""
    payload: object = yaml.load(text, Loader=_StrictLoader)
    if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
        raise TypeError("frontmatter is not a mapping with string keys")
    return payload


def split_tool_list(value: object) -> list[str]:
    """Split a `tools` value into entries, keeping commas inside `Agent(a, b)` together."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [entry.strip() for entry in re.split(r",(?![^(]*\))", value) if entry.strip()]


def assert_no_violations(violations: list[str]) -> None:
    assert not violations, f"{len(violations)} violation(s):\n" + "\n".join(violations)


def _load_doc(path: Path) -> PluginDoc:
    text = path.read_text(encoding="utf-8")
    plugin = path.relative_to(PLUGINS_DIR).parts[0]
    match = _FRONTMATTER.match(text)
    if match is None:
        return PluginDoc(path=path, plugin=plugin, frontmatter_text=None, body=text)
    return PluginDoc(path=path, plugin=plugin, frontmatter_text=match["yaml"], body=match["body"])


def _load_doc_set(pattern: str) -> DocSet:
    docs = tuple(_load_doc(path) for path in sorted(PLUGINS_DIR.glob(pattern)))
    parsed: list[ParsedDoc] = []
    errors: list[str] = []
    for doc in docs:
        if doc.frontmatter_text is None:
            errors.append(f"{doc.relative}: no frontmatter block")
            continue
        try:
            parsed.append(ParsedDoc(doc=doc, frontmatter=parse_frontmatter(doc.frontmatter_text)))
        except (yaml.YAMLError, TypeError) as error:
            errors.append(f"{doc.relative}: {error}")
    return DocSet(docs=docs, parsed=tuple(parsed), parse_errors=tuple(errors))


@pytest.fixture(scope="session")
def agents() -> DocSet:
    doc_set = _load_doc_set("*/agents/*.md")
    assert doc_set.docs, f"no agent files found under {PLUGINS_DIR}"
    return doc_set
