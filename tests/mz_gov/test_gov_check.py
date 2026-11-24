import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/mz-gov/scripts/gov-check.sh"
BASH = shutil.which("bash") or "/bin/bash"

type Check = Callable[..., str]


def fence(
    status: str, signoff: str = "drmozg@2026-11-01T10:00:00Z", model: str = "claude-opus-5-5"
) -> str:
    return (
        "<!-- mz-gov:agdr start -->\n"
        "agdr_id: agdr-0001\ntimestamp: 2026-11-01T09:00:00Z\nagent: gov-artifact-writer\n"
        f"model: {model}\ntrigger: user-prompt\nstatus: {status}\nhuman_signoff: {signoff}\n"
        "<!-- mz-gov:agdr end -->\n"
    )


def nygard(status: str, head: str = "", extra: str = "") -> str:
    return (
        f"# Title\n\n{head}\n## Status\n\n{status}\n\n"
        f"## Context\nc\n## Decision\nd\n## Consequences\nq\n{extra}"
    )


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    for sub in ("decisions", "rfcs", "design"):
        (tmp_path / "docs" / sub).mkdir(parents=True)
    return tmp_path / "docs"


@pytest.fixture
def check(docs: Path) -> Check:
    def _check(*names: str, code: int = 0) -> str:
        result = subprocess.run(
            [BASH, str(SCRIPT), *(str(docs / n) for n in names)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == code, result.stderr
        return result.stdout

    return _check


def block(out: str, name: str) -> str:
    """The report section of one record, or of the repository."""
    head = "## Repository" if name == "Repository" else f"/{name}\n"
    start = out.index(head)
    end = out.find("\n## ", start + len(head))
    return out[start : end if end != -1 else len(out)]


def write(docs: Path, name: str, text: str) -> None:
    (docs / name).write_text(text)


class TestRecord:
    def test_a_signed_decided_adr_has_no_findings(self, docs: Path, check: Check) -> None:
        write(docs, "decisions/0001-a.md", nygard("Accepted", head=fence("accepted")))

        out = block(check("decisions/0001-a.md"), "decisions/0001-a.md")

        assert "- status: accepted (default)" in out
        assert "- human_signoff: signed" in out
        assert "- findings: none" in out

    @pytest.mark.parametrize(
        ("status", "severity"),
        [
            ("accepted", "Critical: human_signoff is pending"),
            ("proposed", "FYI: human_signoff is pending"),
        ],
    )
    def test_a_pending_signoff_is_critical_only_once_decided(
        self, docs: Path, check: Check, status: str, severity: str
    ) -> None:
        write(docs, "decisions/0001-a.md", nygard(status, head=fence(status, signoff="pending")))

        out = block(check("decisions/0001-a.md"), "decisions/0001-a.md")

        assert severity in out
        if status == "proposed":
            assert "Critical" not in out

    @pytest.mark.parametrize(
        ("status", "severity"),
        [
            ("Accepted", "Critical: no AI-provenance fence"),
            ("Proposed", "Nit: no AI-provenance fence"),
        ],
    )
    def test_a_missing_fence_is_critical_only_once_decided(
        self, docs: Path, check: Check, status: str, severity: str
    ) -> None:
        write(docs, "decisions/0001-a.md", nygard(status))

        assert severity in check("decisions/0001-a.md")

    def test_an_executed_fence_counts_as_decided_and_the_status_section_wins(
        self, docs: Path, check: Check
    ) -> None:
        write(
            docs,
            "decisions/0001-a.md",
            nygard("Accepted", head=fence("executed", signoff="pending")),
        )

        out = check("decisions/0001-a.md")

        assert "- status: accepted (default)" in out
        assert "Critical: human_signoff is pending on a record presented as decided" in out

    def test_only_the_leading_status_phrase_counts(self, docs: Path, check: Check) -> None:
        write(docs, "decisions/0001-a.md", nygard("Accepted"))
        write(docs, "decisions/0002-b.md", nygard("Accepted. Supersedes ADR-0001."))

        out = block(check("decisions/0002-b.md"), "decisions/0002-b.md")

        assert "- status: accepted (default)" in out
        assert "- decided: yes" in out

    def test_rfd_states_are_a_fixed_set(self, docs: Path, check: Check) -> None:
        rfd = (
            "---\nstate: {}\n---\n# RFD\n## Summary\n## Problem statement\n"
            "## Proposal\n### A\n### B\n## Open questions\n"
        )
        write(docs, "rfcs/0001-a.md", rfd.format("under review"))
        write(
            docs,
            "rfcs/0002-b.md",
            fence("discussion", signoff="pending").join(["", rfd.format("discussion")]),
        )

        out = check("rfcs/0001-a.md", "rfcs/0002-b.md")

        assert "Critical: status `under review` is not an RFD state" in block(out, "rfcs/0001-a.md")
        # An open RFD is not decided yet, so its pending sign-off is expected.
        assert "Critical" not in block(out, "rfcs/0002-b.md")
        assert "- options listed: 2" in block(out, "rfcs/0002-b.md")

    def test_madr_reads_quoted_front_matter_and_lists_missing_sections(
        self, docs: Path, check: Check
    ) -> None:
        write(
            docs,
            "decisions/0001-a.md",
            '---\nstatus: "accepted"\n---\n# T\n'
            + fence("accepted")
            + "## Context and Problem Statement\n## Considered Options\n- A\n- B\n- C\n",
        )

        out = check("decisions/0001-a.md")

        assert "- type: adr-madr" in out
        assert "- status: accepted (default)" in out
        assert "- options listed: 3" in out
        assert "- sections missing: decision outcome" in out

    def test_a_malformed_fence_gets_nits(self, docs: Path, check: Check) -> None:
        text = nygard(
            "Accepted", head=fence("accepted", model="opus").replace("trigger: user-prompt\n", "")
        )
        write(docs, "decisions/0001-a.md", text)

        out = check("decisions/0001-a.md")

        assert "Nit: provenance fence lacks: trigger." in out
        assert "Nit: model `opus` is a family name" in out
        assert "Critical" not in out

    def test_a_replacement_that_does_not_exist_is_critical(self, docs: Path, check: Check) -> None:
        write(
            docs,
            "decisions/0001-a.md",
            nygard("Superseded by ADR-0009", head=fence("superseded by ADR-0009")),
        )

        assert "Critical: `superseded_by 0009` points to a record that doesn't exist" in check(
            "decisions/0001-a.md"
        )


class TestRepository:
    @pytest.mark.parametrize(
        ("old_status", "flagged"), [("Accepted", True), ("Superseded by ADR-0002", False)]
    )
    def test_a_superseded_record_must_say_so(
        self, docs: Path, check: Check, old_status: str, flagged: bool
    ) -> None:
        write(docs, "decisions/0001-old.md", nygard(old_status))
        write(docs, "decisions/0002-new.md", nygard("Accepted", extra="Supersedes ADR-0001.\n"))

        repo = block(check("decisions/0002-new.md"), "Repository")

        assert ("supersedes 0001-old.md, which still reads `accepted`" in repo) is flagged

    def test_numbering_reports_duplicates_and_gaps_across_the_directory(
        self, docs: Path, check: Check
    ) -> None:
        for name in ("0001-a.md", "0003-b.md", "0003-c.md"):
            write(docs, f"decisions/{name}", nygard("Proposed"))

        repo = block(check("decisions/0001-a.md"), "Repository")

        assert "more than one record numbered 0003: 0003-b.md, 0003-c.md" in repo
        assert "numbering skips 0002." in repo


class TestUsage:
    def test_no_arguments_is_a_usage_error(self, check: Check) -> None:
        check(code=2)

    def test_a_missing_record_fails(self, check: Check) -> None:
        check("decisions/0001-nope.md", code=1)
