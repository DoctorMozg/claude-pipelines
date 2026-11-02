import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins/mz-creative/scripts/forbidden-punctuation.sh"
BASH = shutil.which("bash") or "/bin/bash"
# Spelled by name because ruff flags a literal en dash as a confusable hyphen.
EN_DASH = "\N{EN DASH}"

type Run = Callable[..., subprocess.CompletedProcess[str]]
type Write = Callable[..., str]
type Hits = Callable[[str], list[str]]


@pytest.fixture
def run(tmp_path: Path) -> Run:
    def run_script(*names: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(SCRIPT), *names],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run_script


@pytest.fixture
def write(tmp_path: Path) -> Write:
    def write_file(text: str, name: str = "doc.md") -> str:
        (tmp_path / name).write_text(text, encoding="utf-8")
        return name

    return write_file


@pytest.fixture
def hits(run: Run, write: Write) -> Hits:
    """Hits for one document as `line: name char`, after checking the exit code agrees with them."""

    def check(text: str) -> list[str]:
        result = run(write(text))
        assert result.returncode == (1 if result.stdout else 0), result.stderr
        return [line.removeprefix("doc.md:") for line in result.stdout.splitlines()]

    return check


class TestBannedCharacters:
    @pytest.mark.parametrize(
        ("char", "name"),
        [
            ("—", "em dash"),
            (EN_DASH, "en dash"),
            (";", "semicolon"),
            ("…", "ellipsis"),
            ("→", "arrow"),
            ("←", "arrow"),
            ("⇒", "arrow"),
        ],
    )
    def test_each_character_in_prose_is_reported(self, hits: Hits, char: str, name: str) -> None:
        assert hits(f"A clean line.\nIt works {char} mostly.\n") == [f"2: {name} {char}"]

    def test_each_kind_is_reported_once_per_line(self, hits: Hits) -> None:
        assert hits("One — two; three — four; five.\n") == ["1: em dash —", "1: semicolon ;"]

    def test_arrows_share_one_report_per_line(self, hits: Hits) -> None:
        assert hits("Left ← and right → here.\n") == ["1: arrow →"]

    def test_en_dash_between_words_is_reported(self, hits: Hits) -> None:
        text = f"The Paris{EN_DASH}Berlin train and Paris {EN_DASH} Berlin.\n"
        assert hits(text) == [f"1: en dash {EN_DASH}"]


class TestExemptions:
    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("Run `a; b` now.\n", id="code-span"),
            pytest.param("```\nfoo; bar — baz\n```\n", id="backtick-fence"),
            pytest.param("~~~python\nfoo; bar\n~~~\n", id="tilde-fence"),
            pytest.param("````\n```\ninner — text\n```\n````\n", id="nested-fence"),
            pytest.param("See https://example.com/a;b for more.\n", id="url"),
            pytest.param("> Quoted — as written; verbatim.\n", id="blockquote"),
            pytest.param('He said "wait; no" twice.\n', id="straight-quotes"),
            pytest.param("He said “wait — no” twice.\n", id="curly-quotes"),
            pytest.param(f"Pages 1{EN_DASH}3 and 10{EN_DASH}12.\n", id="digit-range"),
            pytest.param("Fish &amp; chips &#8212; fine.\n", id="html-entity"),
            pytest.param("---\ntitle: a; b\n---\nA clean body.\n", id="frontmatter"),
        ],
    )
    def test_exempt_text_is_not_reported(self, hits: Hits, text: str) -> None:
        assert hits(text) == []

    def test_prose_after_a_closed_fence_is_checked(self, hits: Hits) -> None:
        assert hits("```\ncode; here\n```\nAfter — this.\n") == ["4: em dash —"]

    def test_shorter_fence_does_not_close_a_longer_one(self, hits: Hits) -> None:
        assert hits("````\n```\nstill code; yes\n````\nprose; no\n") == ["5: semicolon ;"]

    def test_unclosed_curly_quote_is_checked(self, hits: Hits) -> None:
        assert hits("He said “wait — no.\n") == ["1: em dash —"]

    def test_dashes_after_first_line_are_not_frontmatter(self, hits: Hits) -> None:
        assert hits("Intro.\n---\nkey; value\n---\n") == ["3: semicolon ;"]


class TestCli:
    def test_clean_file_exits_zero_silently(self, run: Run, write: Write) -> None:
        result = run(write("All clean, really.\n"))
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

    def test_no_arguments_is_a_usage_error(self, run: Run) -> None:
        result = run()
        assert result.returncode == 2
        assert "usage" in result.stderr

    def test_missing_file_is_an_error(self, run: Run) -> None:
        result = run("absent.md")
        assert result.returncode == 2
        assert "cannot read absent.md" in result.stderr
        assert result.stdout == ""

    def test_hits_name_their_file(self, run: Run, write: Write) -> None:
        result = run(write("Clean.\n", "clean.md"), write("Dirty; yes.\n", "dirty.md"))
        assert result.returncode == 1
        assert result.stdout.splitlines() == ["dirty.md:1: semicolon ;"]

    def test_unclosed_fence_does_not_hide_the_next_file(self, run: Run, write: Write) -> None:
        result = run(write("```\ncode; here\n", "open.md"), write("Prose; here.\n", "next.md"))
        assert result.stdout.splitlines() == ["next.md:1: semicolon ;"]
