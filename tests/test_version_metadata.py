from __future__ import annotations

from importlib.metadata import version

import mission_framework


def test_package_level_version_matches_installed_metadata() -> None:
    assert mission_framework.__version__ == "1.0.1"
    assert mission_framework.__version__ == version("orbital-mission-framework")
