from __future__ import annotations

from pathlib import Path


def _release_notes_section(version: str) -> str:
    text = Path("docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
    marker = f"## {version}"
    start = text.index(marker)
    next_section = text.find("\n## ", start + len(marker))
    return text[start:] if next_section == -1 else text[start:next_section]


def test_v1016_release_gate_keeps_checksum_verification_and_ui_health() -> None:
    section = _release_notes_section("v1.0.16")

    assert "python -m mission_framework.cli bundle-verify" in section
    assert "python -m mission_framework.cli ui-health" in section
    assert "outputs\\bvlos_powerline_inspection\\operator_evidence_bundle" in section
