from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from mission_framework.core.constraints import ConstraintReport, ConstraintResult, Severity
from mission_framework.core.json_utils import strict_json_dumps, write_strict_json
from mission_framework.reporting.constraint_report import export_constraint_report_json


def _assert_strict_json(payload: object) -> object:
    encoded = strict_json_dumps(payload, indent=2)
    assert "Infinity" not in encoded
    assert "-Infinity" not in encoded
    assert "NaN" not in encoded
    return json.loads(encoded)


def test_constraint_result_serializes_finite_margins_as_numbers() -> None:
    result = ConstraintResult(
        name="clearance",
        severity=Severity.HARD,
        margins=np.array([4.0, 1.25, 3.0]),
        metadata={"t": np.array([0.0, 10.0, 20.0])},
    )

    payload = result.to_dict()

    assert payload["min_margin"] == pytest.approx(1.25)
    assert payload["max_violation"] == pytest.approx(0.0)
    assert payload["worst_time"] == pytest.approx(10.0)
    assert _assert_strict_json(payload)["min_margin"] == pytest.approx(1.25)


def test_constraint_report_sanitizes_non_finite_margins_for_json() -> None:
    report = ConstraintReport(
        results=[
            ConstraintResult(
                name="empty_margin",
                severity=Severity.HARD,
                margins=np.array([], dtype=float),
            ),
            ConstraintResult(
                name="non_finite_margin",
                severity=Severity.HARD,
                margins=np.array([np.inf, -np.inf, np.nan]),
            ),
        ]
    )

    payload = report.to_jsonable()
    loaded = _assert_strict_json(payload)

    assert loaded["summary"]["total_penalty"] is None
    assert loaded["results"][0]["min_margin"] is None
    assert loaded["results"][1]["min_margin"] is None
    assert loaded["results"][1]["max_violation"] is None


def test_constraint_report_export_writes_strict_json(tmp_path: Path) -> None:
    report = ConstraintReport(
        results=[
            ConstraintResult(
                name="unbounded",
                severity=Severity.SOFT,
                margins=np.array([float("inf")]),
            )
        ]
    )
    out_path = tmp_path / "constraints.json"

    export_constraint_report_json(report, out_path)

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["constraints"][0]["min_margin"] is None
    assert "Infinity" not in out_path.read_text(encoding="utf-8")


def test_strict_json_writer_sanitizes_non_finite_values(tmp_path: Path) -> None:
    out_path = tmp_path / "payload.json"

    write_strict_json(
        out_path,
        {
            "finite": 3.5,
            "nan": float("nan"),
            "inf": float("inf"),
            "array": np.array([1.0, np.nan, np.inf, -np.inf]),
        },
    )

    encoded = out_path.read_text(encoding="utf-8")
    assert "Infinity" not in encoded
    assert "-Infinity" not in encoded
    assert "NaN" not in encoded
    assert json.loads(encoded) == {
        "finite": 3.5,
        "nan": None,
        "inf": None,
        "array": [1.0, None, None, None],
    }


def test_strict_json_writer_rejects_unknown_objects() -> None:
    class Unknown:
        pass

    with pytest.raises(TypeError, match="Unknown"):
        strict_json_dumps({"value": Unknown()})
