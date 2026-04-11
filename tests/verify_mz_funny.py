#!/usr/bin/env python3
"""Structural, safety, and compliance verifier for the `mz-funny` plugin.

Runs the test battery defined in .mz/task/build_do_roast_210859/plan.md
Test Strategy + Verification Criteria sections. Prints one PASS/FAIL
line per test and a final summary + terminal STATUS line.

Exit code: 0 if no FAILs, 1 otherwise.
"""

from __future__ import annotations

import codecs
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Callable

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "mz-funny"
SKILL_PATH = PLUGIN_DIR / "skills" / "do-roast" / "SKILL.md"
PHASES_DIR = PLUGIN_DIR / "skills" / "do-roast" / "phases"
ANALYZE_PATH = PHASES_DIR / "analyze.md"
RENDER_PATH = PHASES_DIR / "render.md"
AGENTS_DIR = PLUGIN_DIR / "agents"
PLUGIN_JSON_PATH = PLUGIN_DIR / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README_PATH = REPO_ROOT / "README.md"

EXPECTED_VERSION = "0.14.0"
EXPECTED_PLUGIN_KEYS = {"description", "license", "name", "version"}
EXPECTED_MARKETPLACE_KEYS = {"category", "description", "keywords", "name", "source", "version"}
EXPECTED_AGENT_KEYS = {"name", "description", "tools", "model", "effort", "maxTurns"}
EXPECTED_SKILL_FRONT_KEYS = {"name", "description", "argument-hint", "allowed-tools"}
EXPECTED_PERSONAS = [
    "caveman", "wh40k-ork", "pirate", "viking", "dwarf", "drill-sergeant", "yoda",
]
EXPECTED_CONSTANTS = [
    "PERSONA_ALLOWLIST", "MAX_PERSONAS", "TASK_DIR",
    "REPORT_DIR", "RESEARCH_CACHE_DIR", "MAX_FINDINGS",
    "DOSSIER_SEVERITY_LABELS",
]
EXPECTED_SKILL_SECTIONS = [
    "## Overview",
    "## When to Use",
    "## Input",
    "## Core Process",
    "## Techniques",
    "## Common Rationalizations",
    "## Red Flags",
    "## Verification",
]
EXPECTED_SEVERITY_LABELS = ["Critical", "Nit", "Optional", "FYI"]

# Whitelist of frontmatter keys we expect to see at the top level. Used by
# the tolerant parser to distinguish a real key line from a sentence that
# happens to contain `word:` (e.g. `Triggers: "roast this"` inside a
# description value).
KNOWN_FRONTMATTER_KEYS = {
    "name", "description", "argument-hint", "allowed-tools",
    "tools", "model", "effort", "maxTurns",
}

# Slur ban list — stored rot13 so the script file never contains verbatim slurs.
# Decoded and compiled into word-boundary regex at runtime.
_SLURS_ROT13 = [
    "avttre",   # n-word root
    "avttn",    # n-word variant
    "jrgonpx",  # w*tback
    "puvax",    # ch*nk
    "tbbx",     # g*ok
    "fcvp",     # sp*c
    "jbt",      # w*g (word-boundary protects real words)
    "qntb",     # d*go
    "xvxr",     # k*ke
    "enturnq",  # r*ghead
    "wnc",      # j*p (word-boundary; won't match 'japan'/'japanese')
    "snttbg",   # f-slur
    "qlxr",     # d-slur (historical)
    "genaal",   # trans slur
    "ergneq",   # r-slur
    "ergneqrq", # r-slur variant
    "fcnfgvp",  # sp-slur (ableist)
    "unysoerrq",# racial historical slur
    "tblvz",    # jewish slur
]

PROTECTED_CLASS_GROUPS = [
    "gay", "trans", "jew", "jewish", "muslim", "christian",
    "black", "white", "asian", "hispanic", "latino",
    "disabled", "autistic",
]

# Outputs
_results: list[tuple[str, str, str]] = []  # (status, name, note)


def record(name: str, status: str, note: str = "") -> None:
    _results.append((status, name, note))


def safe_test(name: str) -> Callable:
    """Decorator that traps exceptions from a test function and records FAIL."""
    def decorator(fn: Callable[[], tuple[str, str] | None]) -> Callable[[], None]:
        def wrapper() -> None:
            try:
                result = fn()
                if result is None:
                    record(name, "PASS", "")
                else:
                    status, note = result
                    record(name, status, note)
            except FileNotFoundError as e:
                record(name, "FAIL", f"file missing: {e}")
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exception_only(type(e), e)[-1].strip()
                record(name, "FAIL", f"exception: {tb}")
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _naive_frontmatter_parse(body: str) -> dict:
    """Tolerant key: value parser that only splits at top-level keys.

    Handles cases yaml.safe_load chokes on, such as an unquoted `Triggers:`
    inside a description value. Only top-level lines whose candidate key
    name is in `KNOWN_FRONTMATTER_KEYS` start a new key; every other line
    is treated as a continuation of the previous value. Without the
    whitelist, a description like `Triggers: "roast this code"` would get
    corrupted into its own `Triggers` key.
    """
    data: dict = {}
    current_key: str | None = None
    for line in body.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        is_new_key = (
            m is not None
            and not line.startswith((" ", "\t"))
            and m.group(1) in KNOWN_FRONTMATTER_KEYS
        )
        if is_new_key:
            assert m is not None  # for type-checkers
            current_key = m.group(1)
            data[current_key] = m.group(2).strip()
        elif current_key is not None:
            data[current_key] = (data[current_key] + " " + line.strip()).strip()
    return data


def parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file. Returns None if absent.

    Uses yaml.safe_load when available; falls back to a tolerant naive
    parser if PyYAML is missing or the frontmatter contains unquoted
    colons inside values (common in skill descriptions).
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    if HAVE_YAML:
        try:
            data = yaml.safe_load(body)
            if isinstance(data, dict):
                return data
        except yaml.YAMLError:
            pass  # fall through to tolerant parser
    return _naive_frontmatter_parse(body)


# ============================================================
# Structural tests
# ============================================================

@safe_test("plugin_json_valid")
def test_plugin_json_valid():
    data = json.loads(read_text(PLUGIN_JSON_PATH))
    keys = set(data.keys())
    if keys != EXPECTED_PLUGIN_KEYS:
        return ("FAIL", f"keys={sorted(keys)} expected={sorted(EXPECTED_PLUGIN_KEYS)}")
    return None


@safe_test("marketplace_json_valid")
def test_marketplace_json_valid():
    data = json.loads(read_text(MARKETPLACE_PATH))
    entries = [p for p in data.get("plugins", []) if p.get("name") == "mz-funny"]
    if not entries:
        return ("FAIL", "no mz-funny entry")
    entry = entries[0]
    keys = set(entry.keys())
    if keys != EXPECTED_MARKETPLACE_KEYS:
        return ("FAIL", f"keys={sorted(keys)} expected={sorted(EXPECTED_MARKETPLACE_KEYS)}")
    category = entry.get("category")
    if category != "creativity":
        return ("FAIL", f"category={category!r} expected='creativity'")
    return None


@safe_test("version_in_sync")
def test_version_in_sync():
    plugin_data = json.loads(read_text(PLUGIN_JSON_PATH))
    market_data = json.loads(read_text(MARKETPLACE_PATH))
    entries = [p for p in market_data.get("plugins", []) if p.get("name") == "mz-funny"]
    if not entries:
        return ("FAIL", "no mz-funny marketplace entry")
    plugin_v = plugin_data.get("version")
    market_meta_v = market_data.get("metadata", {}).get("version")
    market_entry_v = entries[0].get("version")
    versions = {
        "plugin.json": plugin_v,
        "marketplace.metadata": market_meta_v,
        "marketplace.mz-funny": market_entry_v,
    }
    mismatches = {k: v for k, v in versions.items() if v != EXPECTED_VERSION}
    if mismatches:
        return ("FAIL", f"expected {EXPECTED_VERSION}, got {versions}")
    return None


@safe_test("skill_md_frontmatter")
def test_skill_md_frontmatter():
    text = read_text(SKILL_PATH)
    fm = parse_frontmatter(text)
    if fm is None:
        return ("FAIL", "no frontmatter")
    missing = EXPECTED_SKILL_FRONT_KEYS - set(fm.keys())
    if missing:
        return ("FAIL", f"missing fields: {sorted(missing)}")
    return None


@safe_test("skill_md_line_budget")
def test_skill_md_line_budget():
    lines = read_text(SKILL_PATH).splitlines()
    n = len(lines)
    if n > 150:
        return ("FAIL", f"{n} lines > 150")
    return None


@safe_test("phase_file_line_budget")
def test_phase_file_line_budget():
    results = []
    for path in (ANALYZE_PATH, RENDER_PATH):
        n = len(read_text(path).splitlines())
        if n > 400:
            results.append(f"{path.name}={n}")
    if results:
        return ("FAIL", f"over 400: {', '.join(results)}")
    return None


def _iter_agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("roast-*.md"))


@safe_test("agent_frontmatter_shape")
def test_agent_frontmatter_shape():
    agents = _iter_agent_files()
    if not agents:
        return ("FAIL", "no agent files found")
    bad: list[str] = []
    # Personas are dispatched with exactly Read, Grep, Glob. Anything else
    # (WebSearch, WebFetch, Bash, Write) lets a creative voice agent reach
    # outside its evidence envelope and break the fabrication guarantees.
    expected_tools = "Read, Grep, Glob"
    for path in agents:
        fm = parse_frontmatter(read_text(path))
        if fm is None:
            bad.append(f"{path.name}(no frontmatter)")
            continue
        keys = set(fm.keys())
        missing = EXPECTED_AGENT_KEYS - keys
        if missing:
            bad.append(f"{path.name}(missing={sorted(missing)})")
            continue
        tools_val = fm.get("tools")
        if tools_val != expected_tools:
            bad.append(f"{path.name}(tools={tools_val!r} expected={expected_tools!r})")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


@safe_test("agent_name_matches_file")
def test_agent_name_matches_file():
    bad: list[str] = []
    for path in _iter_agent_files():
        fm = parse_frontmatter(read_text(path)) or {}
        name = fm.get("name", "")
        expected = path.stem  # e.g. roast-caveman
        if name != expected:
            bad.append(f"{path.name}: name={name!r} expected={expected!r}")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


@safe_test("agent_line_budget")
def test_agent_line_budget():
    warnings: list[str] = []
    fails: list[str] = []
    for path in _iter_agent_files():
        n = len(read_text(path).splitlines())
        if n > 200:
            fails.append(f"{path.name}={n}")
        elif n > 150:
            warnings.append(f"{path.name}={n}")
    if fails:
        return ("FAIL", f"over 200: {', '.join(fails)}")
    if warnings:
        return ("WARN", f"soft-budget overflow (151-200): {', '.join(warnings)}")
    return None


@safe_test("evidence_contract_anchor")
def test_evidence_contract_anchor():
    bad: list[str] = []
    for path in _iter_agent_files():
        text = read_text(path)
        ec_idx = text.find("## Evidence Contract")
        lens_idx = text.find("## Your Lens")
        if ec_idx == -1:
            bad.append(f"{path.name}: no ## Evidence Contract")
            continue
        if lens_idx != -1 and ec_idx >= lens_idx:
            bad.append(f"{path.name}: Evidence Contract not before Your Lens")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


@safe_test("safety_floor_anchor")
def test_safety_floor_anchor():
    bad: list[str] = []
    for path in _iter_agent_files():
        text = read_text(path)
        lines = text.splitlines()
        h2_positions = [
            (i, line) for i, line in enumerate(lines)
            if re.match(r"^##\s+\S", line)
        ]
        safety_indices = [
            i for i, line in h2_positions
            if line.strip().lower().startswith("## safety floor")
        ]
        if not safety_indices:
            bad.append(f"{path.name}: no ## Safety Floor")
            continue
        last_safety = safety_indices[-1]
        trailing_h2 = [
            line for i, line in h2_positions if i > last_safety
        ]
        if trailing_h2:
            bad.append(f"{path.name}: Safety Floor not last (trailing: {trailing_h2[0]!r})")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


@safe_test("skill_sections_present")
def test_skill_sections_present():
    text = read_text(SKILL_PATH)
    missing = [s for s in EXPECTED_SKILL_SECTIONS if s not in text]
    if missing:
        return ("FAIL", f"missing sections: {missing}")
    return None


@safe_test("phase_table_present")
def test_phase_table_present():
    text = read_text(SKILL_PATH)
    # Look for a table row that uses 'Phase' as a column header.
    if re.search(r"\|\s*Phase\s*\|", text) or re.search(r"\|\s*#\s*\|\s*Phase\s*\|", text):
        return None
    return ("FAIL", "no table with a 'Phase' column header")


@safe_test("constants_defined")
def test_constants_defined():
    text = read_text(SKILL_PATH)
    missing = [c for c in EXPECTED_CONSTANTS if c not in text]
    if missing:
        return ("FAIL", f"missing constants: {missing}")
    return None


@safe_test("phase_refs_resolve")
def test_phase_refs_resolve():
    text = read_text(SKILL_PATH)
    refs = re.findall(r"phases/([A-Za-z0-9_\-]+\.md)", text)
    bad: list[str] = []
    for ref in set(refs):
        if not (PHASES_DIR / ref).exists():
            bad.append(ref)
    if bad:
        return ("FAIL", f"missing phase files: {bad}")
    return None


def _extract_persona_allowlist(skill_text: str) -> list[str]:
    """Parse PERSONA_ALLOWLIST: `["a", "b", ...]` from SKILL.md."""
    m = re.search(
        r"PERSONA_ALLOWLIST.*?\[([^\]]*)\]",
        skill_text,
        re.DOTALL,
    )
    if not m:
        return []
    body = m.group(1)
    return re.findall(r'"([^"]+)"', body)


def _extract_persona_table(skill_text: str) -> str:
    """Return the text of the `## Available Personas` section."""
    m = re.search(
        r"##\s+Available Personas\s*\n(.*?)(?=\n##\s|\Z)",
        skill_text,
        re.DOTALL,
    )
    return m.group(1) if m else ""


@safe_test("persona_allowlist_in_table")
def test_persona_allowlist_in_table():
    text = read_text(SKILL_PATH)
    allowlist = _extract_persona_allowlist(text)
    if not allowlist:
        return ("FAIL", "could not parse PERSONA_ALLOWLIST")
    table_text = _extract_persona_table(text)
    if not table_text:
        return ("FAIL", "no ## Available Personas section")
    missing = [p for p in allowlist if p not in table_text]
    if missing:
        return ("FAIL", f"personas missing from table: {missing}")
    return None


# ============================================================
# Safety tests
# ============================================================

def _decode_slur_list() -> list[str]:
    return [codecs.encode(w, "rot_13") for w in _SLURS_ROT13]


def _safety_scan_files() -> list[Path]:
    files: list[Path] = []
    files.extend(_iter_agent_files())
    # Include SKILL.md so the orchestrator file is held to the same slur +
    # protected-class bar as the agent files (kept in sync with the file
    # list in test_no_real_person_refs below).
    for p in (ANALYZE_PATH, RENDER_PATH, SKILL_PATH):
        if p.exists():
            files.append(p)
    return files


@safe_test("no_slurs_in_agents")
def test_no_slurs_in_agents():
    slurs = _decode_slur_list()
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(s) for s in slurs) + r")\b",
        re.IGNORECASE,
    )
    hits: list[str] = []
    for path in _safety_scan_files():
        text = read_text(path)
        for i, line in enumerate(text.splitlines(), 1):
            m = pattern.search(line)
            if m:
                # Mask the matched substring in the report so the output is not a slur.
                masked_line = line[: m.start()] + "[REDACTED]" + line[m.end():]
                hits.append(f"{path.name}:{i}: {masked_line.strip()[:80]}")
    if hits:
        return ("FAIL", f"{len(hits)} hit(s): " + " | ".join(hits[:5]))
    return None


@safe_test("no_protected_class_attacks")
def test_no_protected_class_attacks():
    # Hard-fail patterns: "all X are" style blanket attacks.
    hard_patterns = [
        re.compile(r"\ball\s+women\s+are\b", re.IGNORECASE),
        re.compile(r"\ball\s+men\s+are\b", re.IGNORECASE),
        re.compile(
            r"\b(" + "|".join(PROTECTED_CLASS_GROUPS) + r")\s+(people|men|women)\s+(are|can't|cannot|never)\b",
            re.IGNORECASE,
        ),
    ]
    fails: list[str] = []
    # Soft pattern: protected-class noun mentions (for INFO review only).
    soft_pattern = re.compile(
        r"\b(" + "|".join(PROTECTED_CLASS_GROUPS) + r")\s+(people|men|women)\b",
        re.IGNORECASE,
    )
    soft_hits: list[str] = []
    for path in _safety_scan_files():
        text = read_text(path)
        for i, line in enumerate(text.splitlines(), 1):
            for pat in hard_patterns:
                if pat.search(line):
                    fails.append(f"{path.name}:{i}: {line.strip()[:80]}")
                    break
            if soft_pattern.search(line):
                soft_hits.append(f"{path.name}:{i}")
    if fails:
        return ("FAIL", f"hard-pattern hits: {fails[:3]}")
    if soft_hits:
        return ("INFO", f"{len(soft_hits)} protected-class mention(s) for manual review: {soft_hits[:5]}")
    return None


@safe_test("no_real_person_refs")
def test_no_real_person_refs():
    targets = re.compile(
        r"(git\s+blame|git\s+log\s+--author|author\s*:)",
        re.IGNORECASE,
    )
    # Only strict prohibition markers. Loose markers like "do not", "don't",
    # "never", or "red flag" are too common in skill/agent prose and would
    # suppress genuine author-reference leaks that happen to sit within 8
    # lines of any such phrase.
    prohibition_markers = [
        "prohibited", "forbidden", "prohibition",
        "must not", "may not",
        "safety floor", "no author", "author-attack",
        "no git blame", "do not run git blame", "do not use git blame",
    ]
    # Section headers that categorically establish a prohibition context.
    # These are structural signals (H1/H2/H3), not loose prose — they do
    # not trigger the false-positive problem that the loose-marker list has.
    prohibition_section_pattern = re.compile(
        r"^#{1,6}\s+(safety floor|red flags?|author-attack prohibition|"
        r"prohibition|banned|forbidden)\b",
        re.IGNORECASE,
    )
    bad_hits: list[str] = []
    total_hits = 0
    files: list[Path] = []
    files.extend(_iter_agent_files())
    if ANALYZE_PATH.exists():
        files.append(ANALYZE_PATH)
    if RENDER_PATH.exists():
        files.append(RENDER_PATH)
    if SKILL_PATH.exists():
        files.append(SKILL_PATH)
    for path in files:
        text = read_text(path)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not targets.search(line):
                continue
            total_hits += 1
            # Narrowed to +/- 5 lines to reduce false suppression — the
            # prohibition marker must sit inside the same paragraph/block.
            window_start = max(0, i - 5)
            window_end = min(len(lines), i + 6)
            window_lines = lines[window_start:window_end]
            window_lower = "\n".join(window_lines).lower()
            has_prohibition_marker = any(
                marker in window_lower for marker in prohibition_markers
            )
            has_prohibition_section = any(
                prohibition_section_pattern.match(wl) for wl in window_lines
            )
            if not (has_prohibition_marker or has_prohibition_section):
                bad_hits.append(f"{path.name}:{i + 1}: {line.strip()[:80]}")
    if bad_hits:
        return ("FAIL", f"{len(bad_hits)} unscoped hit(s): " + " | ".join(bad_hits[:3]))
    return None  # all hits were inside prohibition blocks (or none)


# ============================================================
# Compliance tests
# ============================================================

@safe_test("description_cso_compliant")
def test_description_cso_compliant():
    text = read_text(SKILL_PATH)
    fm = parse_frontmatter(text) or {}
    desc = fm.get("description", "")
    if not isinstance(desc, str):
        return ("FAIL", f"description not a string: {type(desc).__name__}")
    issues: list[str] = []
    if len(desc) > 250:
        issues.append(f"len={len(desc)} > 250")
    if "always invoke when" not in desc.lower():
        issues.append("no 'ALWAYS invoke when'")
    quoted = re.findall(r'"([^"]+)"', desc)
    if len(quoted) < 2:
        issues.append(f"only {len(quoted)} quoted trigger phrases")
    if re.search(r"this skill will", desc, re.IGNORECASE):
        issues.append("ends with workflow summary ('This skill will...')")
    if issues:
        return ("FAIL", "; ".join(issues))
    return None


@safe_test("agent_descriptions_cso")
def test_agent_descriptions_cso():
    bad: list[str] = []
    for path in _iter_agent_files():
        fm = parse_frontmatter(read_text(path)) or {}
        desc = fm.get("description", "")
        if not isinstance(desc, str):
            bad.append(f"{path.name}: not a string")
            continue
        if len(desc) > 250:
            bad.append(f"{path.name}: len={len(desc)} > 250")
        if re.search(r"\bI\s+(am|will|can|have|do)\b", desc):
            bad.append(f"{path.name}: first-person 'I ...'")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


@safe_test("severity_labels_used")
def test_severity_labels_used():
    text = read_text(ANALYZE_PATH)
    missing = [lbl for lbl in EXPECTED_SEVERITY_LABELS if lbl not in text]
    if missing:
        return ("FAIL", f"missing labels: {missing}")
    if "DOSSIER_SEVERITY_LABELS" not in text:
        return ("FAIL", "DOSSIER_SEVERITY_LABELS not referenced in analyze.md")
    return None


@safe_test("four_status_protocol")
def test_four_status_protocol():
    text = read_text(RENDER_PATH)
    # Look for "DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED" in any order.
    required_tokens = ["DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"]
    missing = [t for t in required_tokens if t not in text]
    if missing:
        return ("FAIL", f"missing status tokens: {missing}")
    if "STATUS:" not in text:
        return ("FAIL", "no 'STATUS:' prefix")
    return None


@safe_test("source_hierarchy_declared")
def test_source_hierarchy_declared():
    text = read_text(ANALYZE_PATH)
    lower = text.lower()
    if "source hierarchy" not in lower and "source ladder" not in lower:
        return ("FAIL", "no 'source hierarchy/ladder' phrase")
    # `ai-generated` and `ai generated` are the same concept with different
    # punctuation — collapse them into one required token so the stricter
    # check does not penalize a legitimate stylistic choice.
    required_tokens = [
        ["stack overflow"],
        ["ai-generated", "ai generated"],
        ["undated blog"],
    ]
    missing = [alts[0] for alts in required_tokens if not any(a in lower for a in alts)]
    if missing:
        return ("FAIL", f"missing ban-list tokens: {missing}")
    return None


@safe_test("author_attack_prohibition_present")
def test_author_attack_prohibition_present():
    text = read_text(ANALYZE_PATH)
    # Exact-ish match (case-insensitive, whitespace-tolerant).
    pattern = re.compile(
        r"do\s+not\s+run\s+git\s+blame",
        re.IGNORECASE,
    )
    if not pattern.search(text):
        return ("FAIL", "missing 'Do NOT run git blame' phrase")
    # Also check the other two commands named in the prohibition.
    if "git log --author" not in text.lower():
        return ("FAIL", "prohibition missing 'git log --author'")
    return None


@safe_test("dispatch_prompt_inlines_dossier")
def test_dispatch_prompt_inlines_dossier():
    text = read_text(RENDER_PATH)
    lower = text.lower()
    if "dispatch prompt" not in lower:
        return ("FAIL", "no 'dispatch prompt' section heading")
    markers = ["inline", "verbatim", "full contents", "complete verbatim", "substitut", "not a path"]
    hits = [m for m in markers if m in lower]
    if len(hits) < 2:
        return ("FAIL", f"only {len(hits)} inlining marker(s): {hits}")
    return None


@safe_test("collision_handling_present")
def test_collision_handling_present():
    text = read_text(RENDER_PATH)
    if "_v2" not in text and "_v10" not in text:
        return ("FAIL", "no _v2 / _v10 collision language")
    return None


@safe_test("readme_section_present")
def test_readme_section_present():
    text = read_text(README_PATH)
    patterns = [
        re.compile(r"###\s*\[mz-funny\]"),
        re.compile(r"###\s*\[`mz-funny`\]"),
    ]
    if not any(p.search(text) for p in patterns):
        return ("FAIL", "no mz-funny README section header")
    return None


@safe_test("approval_gate_five_elements")
def test_approval_gate_five_elements():
    text = read_text(SKILL_PATH)
    # Extract the Phase 0.5 section body (everything from the Phase 0.5
    # heading to the next top-level heading of equal or greater prominence).
    m = re.search(
        r"##\s+Phase 0\.5.*?(?=\n##\s|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        return ("FAIL", "no '## Phase 0.5' section in SKILL.md")
    section = m.group(0).lower()
    # Rule 1 five-element gate — each element has one or more accepted markers.
    elements = {
        "delegation-guard": [
            "delegation guard", "not be delegated", "not a subagent",
            "must not be delegated",
        ],
        "presentation": [
            "presentation", "i resolved", "present:",
        ],
        "ask-user-question": [
            "askuserquestion",
        ],
        "approve-reject-feedback": None,  # handled specially below
        "loop": [
            "loop", "repeat until", "never proceed without",
        ],
    }
    missing: list[str] = []
    for name, markers in elements.items():
        if name == "approve-reject-feedback":
            # All three tokens must be present, in any order.
            if not ("approve" in section and "reject" in section and "feedback" in section):
                missing.append(name)
            continue
        assert markers is not None
        if not any(marker in section for marker in markers):
            missing.append(name)
    if missing:
        return ("FAIL", f"missing Rule 1 elements: {missing}")
    return None


# ============================================================
# Integration tests
# ============================================================

@safe_test("orchestrator_to_persona_handoff")
def test_orchestrator_to_persona_handoff():
    text = read_text(SKILL_PATH)
    allowlist = _extract_persona_allowlist(text)
    if not allowlist:
        return ("FAIL", "could not parse PERSONA_ALLOWLIST")
    # Forward direction: every allowlisted persona must have an agent file.
    missing_files: list[str] = []
    for persona in allowlist:
        agent_path = AGENTS_DIR / f"roast-{persona}.md"
        if not agent_path.exists():
            missing_files.append(f"roast-{persona}.md")
    # Reverse direction: every roast-*.md file must correspond to an
    # allowlisted persona (no orphan agents left in the directory).
    allowlist_set = set(allowlist)
    orphan_files: list[str] = []
    for agent_path in _iter_agent_files():
        # path.stem is e.g. `roast-caveman`; strip the `roast-` prefix.
        stem = agent_path.stem
        if not stem.startswith("roast-"):
            continue
        persona = stem[len("roast-"):]
        if persona not in allowlist_set:
            orphan_files.append(agent_path.name)
    problems: list[str] = []
    if missing_files:
        problems.append(f"allowlist->no_file: {missing_files}")
    if orphan_files:
        problems.append(f"file->not_in_allowlist: {orphan_files}")
    if problems:
        return ("FAIL", "; ".join(problems))
    return None


@safe_test("analyze_to_render_handoff")
def test_analyze_to_render_handoff():
    analyze_text = read_text(ANALYZE_PATH)
    render_text = read_text(RENDER_PATH)
    # Both phases must reference `dossier.md` so the artifact name aligns.
    problems: list[str] = []
    if "dossier.md" not in analyze_text:
        problems.append("analyze.md missing 'dossier.md' reference")
    if "dossier.md" not in render_text:
        problems.append("render.md missing 'dossier.md' reference")
    # Both phases must use the same TASK_DIR prefix convention. Fail if one
    # file uses the `TASK_DIR` constant and the other hardcodes `.mz/task/`.
    analyze_uses_constant = "TASK_DIR" in analyze_text
    render_uses_constant = "TASK_DIR" in render_text
    analyze_hardcodes = ".mz/task/" in analyze_text
    render_hardcodes = ".mz/task/" in render_text
    if analyze_uses_constant != render_uses_constant:
        problems.append(
            f"TASK_DIR constant usage mismatch: "
            f"analyze={analyze_uses_constant} render={render_uses_constant}"
        )
    # Catch the case where one file uses the constant and the other hardcodes
    # the literal path — they diverge even if both reference dossier.md.
    if analyze_uses_constant and render_hardcodes and not render_uses_constant:
        problems.append("analyze.md uses TASK_DIR but render.md hardcodes .mz/task/")
    if render_uses_constant and analyze_hardcodes and not analyze_uses_constant:
        problems.append("render.md uses TASK_DIR but analyze.md hardcodes .mz/task/")
    if problems:
        return ("FAIL", "; ".join(problems))
    return None


@safe_test("dossier_contract")
def test_dossier_contract():
    analyze_text = read_text(ANALYZE_PATH)
    # analyze.md must declare the `## Finding N` header shape (either a
    # literal `## Finding 1` example row in the schema block or the
    # parameterized `## Finding N` form in the contract prose).
    finding_header_pattern = re.compile(r"##\s+Finding\s+[0-9N]\b")
    if not finding_header_pattern.search(analyze_text):
        return ("FAIL", "analyze.md missing '## Finding N' / '## Finding 1' header format")
    # Every persona agent must reference the `(Finding ` citation format in
    # either its Evidence Contract or How You Work section. Grep the whole
    # file body — the section names are enforced by other tests.
    bad: list[str] = []
    for path in _iter_agent_files():
        text = read_text(path)
        if "(Finding " not in text:
            bad.append(f"{path.name}: no '(Finding ' citation")
    if bad:
        return ("FAIL", "; ".join(bad))
    return None


# ============================================================
# Runner
# ============================================================

TESTS: list[Callable[[], None]] = [
    test_plugin_json_valid,
    test_marketplace_json_valid,
    test_version_in_sync,
    test_skill_md_frontmatter,
    test_skill_md_line_budget,
    test_phase_file_line_budget,
    test_agent_frontmatter_shape,
    test_agent_name_matches_file,
    test_agent_line_budget,
    test_evidence_contract_anchor,
    test_safety_floor_anchor,
    test_skill_sections_present,
    test_phase_table_present,
    test_constants_defined,
    test_phase_refs_resolve,
    test_persona_allowlist_in_table,
    test_no_slurs_in_agents,
    test_no_protected_class_attacks,
    test_no_real_person_refs,
    test_description_cso_compliant,
    test_agent_descriptions_cso,
    test_severity_labels_used,
    test_four_status_protocol,
    test_source_hierarchy_declared,
    test_author_attack_prohibition_present,
    test_dispatch_prompt_inlines_dossier,
    test_collision_handling_present,
    test_readme_section_present,
    test_approval_gate_five_elements,
    test_orchestrator_to_persona_handoff,
    test_analyze_to_render_handoff,
    test_dossier_contract,
]


def main() -> int:
    for test_fn in TESTS:
        test_fn()

    passed = sum(1 for r in _results if r[0] == "PASS")
    failed = sum(1 for r in _results if r[0] == "FAIL")
    warned = sum(1 for r in _results if r[0] == "WARN")
    info = sum(1 for r in _results if r[0] == "INFO")

    for status, name, note in _results:
        line = f"{status:4s} {name}"
        if note:
            line += f" — {note}"
        print(line)

    print()
    summary = f"{passed} passed, {failed} failed, {warned} warnings, {info} info"

    # STATUS must track exit code: BLOCKED <-> 1, DONE/DONE_WITH_CONCERNS <-> 0.
    if failed > 0:
        print(summary)
        print("STATUS: BLOCKED")
        return 1
    if warned > 0:
        print(summary)
        print("STATUS: DONE_WITH_CONCERNS")
        return 0
    print(summary)
    print("STATUS: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
