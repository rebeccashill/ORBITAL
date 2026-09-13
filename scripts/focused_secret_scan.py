from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple

DEFAULT_SCAN_PATHS = (
    "README.md",
    "docs",
    "examples",
    "outputs/bvlos_powerline_inspection",
)

TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".kml",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}

MAX_TEXT_BYTES = 2_000_000

SECRET_PATTERNS = (
    ("GitHub classic token", re.compile(r"\bghp_[A-Za-z0-9_]{30,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    (
        "Private key block",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |)?PRIVATE KEY-----"),
    ),
)


class Finding(NamedTuple):
    path: Path
    line_number: int
    label: str
    excerpt: str


def _candidate_files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            candidates = [path]
        else:
            candidates = [item for item in path.rglob("*") if item.is_file()]
        for candidate in candidates:
            if candidate.name == Path(__file__).name:
                continue
            if candidate.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if candidate.stat().st_size > MAX_TEXT_BYTES:
                    continue
            except OSError:
                continue
            yield candidate


def _redact(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 16:
        return stripped
    return f"{stripped[:8]}...{stripped[-4:]}"


def scan_paths(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in _candidate_files(paths):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for label, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(
                        Finding(
                            path=path,
                            line_number=line_number,
                            label=label,
                            excerpt=_redact(match.group(0)),
                        )
                    )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a focused secret scan over ORBITAL release-facing docs, examples, "
            "and BVLOS demo outputs."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=list(DEFAULT_SCAN_PATHS),
        help="Paths to scan. Defaults to README, docs, examples, and BVLOS demo outputs.",
    )
    args = parser.parse_args(argv)

    findings = scan_paths(Path(path) for path in args.paths)
    if findings:
        print("Focused secret scan found possible secrets:", file=sys.stderr)
        for finding in findings:
            print(
                f"- {finding.path}:{finding.line_number}: " f"{finding.label} ({finding.excerpt})",
                file=sys.stderr,
            )
        return 1

    print("Focused secret scan passed: no high-signal secret patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
