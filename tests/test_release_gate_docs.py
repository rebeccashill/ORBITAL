from __future__ import annotations

from pathlib import Path


def _release_notes_section(version: str) -> str:
    text = Path("docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
    marker = f"## {version}"
    start = text.index(marker)
    next_section = text.find("\n## ", start + len(marker))
    return text[start:] if next_section == -1 else text[start:next_section]


def test_v1017_release_gate_keeps_checksum_verification_and_ui_health() -> None:
    section = _release_notes_section("v1.0.17")
    normalized = " ".join(section.split())

    assert "python -m mission_framework.cli bundle-verify" in section
    assert "python -m mission_framework.cli ui-health" in section
    assert "validates every committed BVLOS fixture bundle" in normalized
    assert "ready, stale-evidence, missing-artifact, and modify/no-go states" in section
    assert "artifact-link" in section
