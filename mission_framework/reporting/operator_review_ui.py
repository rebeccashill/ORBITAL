from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence


def _text(value: Any, default: str = "not provided") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered if rendered else default


def _fmt_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _text(value)
    suffix = f" {unit}" if unit else ""
    if 0.0 < abs(number) < 1.0:
        return f"{number:.3g}{suffix}"
    return f"{number:.1f}{suffix}"


def _pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.1f} %"


def _counted_score(block: Mapping[str, Any], *, total_label: str) -> str:
    score = _pct(block.get("score"))
    if total_label == "artifacts":
        present = block.get("present_artifacts", 0)
        total = block.get("total_artifacts", 0)
    else:
        present = block.get("documented_fields", 0)
        total = block.get("total_fields", 0)
    return f"{score} ({present} / {total} {total_label})"


def _status_label(value: Any) -> str:
    normalized = _text(value, "unknown").replace("_", " ").replace("-", " ").upper()
    return normalized


def _status_class(value: Any) -> str:
    normalized = _text(value, "unknown").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in {"go", "pass", "clear", "ready", "ready_for_review", "configured_source"}:
        return "status-good"
    if normalized in {"review_required", "operator_action_required", "warning", "fallback_used"}:
        return "status-review"
    if normalized in {"modify", "fail", "failed", "elevated_risk"}:
        return "status-bad"
    return "status-neutral"


def _margin_summary(top: Mapping[str, Any]) -> str:
    if not top:
        return "not available"
    raw_margin = top.get("margin")
    margin: Mapping[str, Any] = raw_margin if isinstance(raw_margin, Mapping) else {}
    label = _text(top.get("label") or top.get("id"), "Constraint")
    status = _status_label(top.get("status"))
    return f"{label}, {status}, margin {_fmt_value(margin.get('value'), margin.get('unit') or '')}"


def _dashboard_verdict(
    *,
    mission_status: str,
    regulatory_state: str,
    missing_evidence_count: int,
    warning_count: int,
) -> dict[str, str]:
    mission_key = mission_status.replace(" ", "_")
    regulatory_key = regulatory_state.replace(" ", "_")
    if mission_key != "GO":
        return {
            "label": "MODIFY",
            "meaning": "Modeled constraints do not support release as configured.",
            "next_action": (
                "Modify the route, assumptions, or constraints, then regenerate the "
                "evidence bundle before operator review."
            ),
        }
    if (
        regulatory_key == "OPERATOR_ACTION_REQUIRED"
        or missing_evidence_count > 0
        or warning_count > 0
    ):
        return {
            "label": "REVIEW REQUIRED",
            "meaning": (
                "Modeled feasibility is acceptable, but operator, regulatory, or "
                "evidence review items remain."
            ),
            "next_action": (
                "Complete the listed review items, confirm regulatory readiness outside "
                "ORBITAL, then record the operator decision."
            ),
        }
    return {
        "label": "GO",
        "meaning": "Modeled feasibility and bundle evidence are ready for normal operator review.",
        "next_action": (
            "Proceed to normal operator review, verify checksums, and archive the "
            "evidence bundle."
        ),
    }


def _artifact_entry(manifest: Mapping[str, Any], ids: Sequence[str]) -> Mapping[str, Any]:
    entries = list(manifest.get("artifacts", []) or []) + list(
        manifest.get("generated_artifacts", []) or []
    )
    for artifact_id in ids:
        for entry in entries:
            if entry.get("id") == artifact_id:
                return entry
    return {}


def _href(bundle_path: Any) -> str:
    path = _text(bundle_path, "").replace("\\", "/").replace(" ", "%20")
    return escape(path, quote=True)


def _artifact_link(manifest: Mapping[str, Any], ids: Sequence[str], label: str) -> str:
    entry = _artifact_entry(manifest, ids)
    if entry and entry.get("present") and entry.get("bundle_path"):
        return f'<a href="{_href(entry.get("bundle_path"))}">{escape(label)}</a>'
    return f'<span class="unavailable">{escape(label)} unavailable</span>'


def _stat_card(label: str, value: Any, detail: str = "", class_name: str = "") -> str:
    css = f" signal {class_name}".strip()
    detail_html = f"<p>{escape(detail)}</p>" if detail else ""
    return (
        f'<article class="{css}">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(_text(value))}</strong>"
        f"{detail_html}"
        "</article>"
    )


def _route_preview(manifest: Mapping[str, Any]) -> str:
    entry = _artifact_entry(manifest, ("flight_path_plot",))
    if entry and entry.get("present") and entry.get("bundle_path"):
        return (
            '<figure class="route-preview">'
            f'<img src="{_href(entry.get("bundle_path"))}" '
            'alt="Flight path plot from the evidence bundle">'
            "<figcaption>Route preview from the generated evidence bundle.</figcaption>"
            "</figure>"
        )
    return (
        '<div class="route-preview route-missing">'
        "<strong>Route preview unavailable</strong>"
        "<p>The flight path plot is missing from this bundle.</p>"
        "</div>"
    )


def format_operator_review_ui_html(manifest: Mapping[str, Any]) -> str:
    """Render the read-only local operator review UI as a standalone HTML document."""
    audit = manifest.get("constraint_audit") or {}
    readiness = manifest.get("regulatory_readiness") or {}
    completeness = manifest.get("bundle_completeness") or {}
    regulatory_completeness = manifest.get("regulatory_documentation_completeness") or {}
    trust = manifest.get("trust_defensibility") or {}
    weather = trust.get("weather_fallback_status") or {}
    robustness = trust.get("uncertainty_robustness_status") or {}
    evidence_warnings = trust.get("evidence_warning_summary") or {}
    missing_evidence = manifest.get("missing_evidence") or []
    bundle_warnings = manifest.get("bundle_warnings") or []
    review = manifest.get("operator_review") or {}

    mission_status = _status_label(audit.get("status"))
    mission_risk = _status_label(audit.get("mission_risk"))
    regulatory_state = _status_label(readiness.get("readiness_state") or readiness.get("status"))
    warning_count = int(evidence_warnings.get("bundle_warnings", len(bundle_warnings)) or 0)
    missing_count = int(evidence_warnings.get("missing_evidence", len(missing_evidence)) or 0)
    stale_count = int(evidence_warnings.get("stale_artifacts", 0) or 0)
    missing_artifact_count = int(evidence_warnings.get("missing_artifacts", 0) or 0)
    verdict = _dashboard_verdict(
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        missing_evidence_count=missing_count,
        warning_count=warning_count,
    )
    mission_name = (
        audit.get("mission_id") or Path(_text(manifest.get("scenario_path"), "scenario")).stem
    )
    top_summary = _margin_summary(audit.get("top_limiting_constraint") or {})
    evidence_completeness = _counted_score(completeness, total_label="artifacts")
    regulatory_doc_completeness = _counted_score(regulatory_completeness, total_label="fields")
    weather_status = _status_label(weather.get("status"))
    weather_summary = _text(weather.get("summary"), "No weather fallback status captured.")
    robustness_status = _status_label(robustness.get("status"))
    robustness_summary = _text(
        robustness.get("summary"), "No robustness / uncertainty status captured."
    )
    evidence_warning_summary = _text(
        evidence_warnings.get("summary"),
        f"{missing_artifact_count} missing artifact(s), {stale_count} stale artifact(s), "
        f"{missing_count} missing evidence item(s), {warning_count} bundle warning(s)",
    )

    cards = "\n".join(
        [
            _stat_card(
                "Modeled mission status", mission_status, class_name=_status_class(mission_status)
            ),
            _stat_card("Mission risk", mission_risk, class_name=_status_class(mission_risk)),
            _stat_card("Top limiting constraint", top_summary),
            _stat_card(
                "Regulatory readiness", regulatory_state, class_name=_status_class(regulatory_state)
            ),
            _stat_card("Evidence completeness", evidence_completeness),
            _stat_card("Regulatory documentation", regulatory_doc_completeness),
            _stat_card(
                "Weather fallback", weather_status, weather_summary, _status_class(weather_status)
            ),
            _stat_card(
                "Robustness / uncertainty",
                robustness_status,
                robustness_summary,
                _status_class(robustness_status),
            ),
            _stat_card("Missing evidence", f"{missing_count} item(s)"),
            _stat_card(
                "Evidence warnings",
                evidence_warning_summary,
                class_name=_status_class(evidence_warnings.get("status")),
            ),
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ORBITAL Operator Review</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #17202a;
      background: #f5f7f9;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 16px;
      line-height: 1.45;
    }}
    a {{ color: #0f5f9f; font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{ min-height: 100vh; }}
    .topbar {{
      background: #ffffff;
      border-bottom: 1px solid #d8dee7;
      padding: 18px 28px;
    }}
    .topbar strong {{ display: block; font-size: 20px; }}
    .topbar span {{ color: #607080; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 24px; }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
      gap: 20px;
      align-items: stretch;
    }}
    .verdict, .panel, .signal, .route-preview {{
      background: #ffffff;
      border: 1px solid #d8dee7;
      border-radius: 8px;
    }}
    .verdict {{ padding: 24px; }}
    .eyebrow {{
      color: #607080;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{ margin: 8px 0 10px; font-size: 34px; line-height: 1.1; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 21px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }}
    .verdict-badge {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      border-radius: 8px;
      padding: 5px 10px;
      font-weight: 800;
      border: 1px solid currentColor;
    }}
    .status-good {{ color: #14633f; background: #edf8f2; border-color: #9fd4b6; }}
    .status-review {{ color: #7a4a00; background: #fff6df; border-color: #e6c46c; }}
    .status-bad {{ color: #9b1c1c; background: #fff0f0; border-color: #e5a1a1; }}
    .status-neutral {{ color: #425466; background: #eef3f7; border-color: #c9d4df; }}
    .next-action {{
      margin-top: 18px;
      padding: 14px;
      border-left: 4px solid #0f5f9f;
      background: #eef6fc;
      border-radius: 6px;
    }}
    .signals {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .signal {{ padding: 14px; min-height: 112px; overflow-wrap: anywhere; }}
    .signal span {{ display: block; color: #607080; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .signal strong {{ display: block; margin-top: 6px; font-size: 17px; }}
    .signal p {{ margin: 8px 0 0; color: #425466; font-size: 13px; }}
    .side-stack {{ display: grid; gap: 14px; }}
    .panel {{ padding: 18px; }}
    .boundary-list {{ margin: 0; padding-left: 18px; }}
    .boundary-list li {{ margin: 8px 0; }}
    .route-preview {{ margin: 0; padding: 14px; }}
    .route-preview img {{ display: block; width: 100%; height: auto; border-radius: 6px; border: 1px solid #d8dee7; }}
    .route-preview figcaption {{ margin-top: 8px; color: #607080; font-size: 13px; }}
    .route-missing {{ color: #607080; }}
    .quick-links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .quick-links a, .quick-links .unavailable {{
      border: 1px solid #c9d4df;
      border-radius: 8px;
      padding: 8px 10px;
      background: #f9fbfc;
    }}
    .unavailable {{ color: #6f7d8a; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .meta-grid div {{ padding: 10px; background: #f9fbfc; border-radius: 6px; border: 1px solid #e3e8ee; }}
    .meta-grid span {{ display: block; color: #607080; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .meta-grid strong {{ display: block; margin-top: 4px; }}
    @media (max-width: 920px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .signals {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 620px) {{
      main {{ padding: 16px; }}
      .topbar {{ padding: 14px 16px; }}
      h1 {{ font-size: 28px; }}
      .signals, .meta-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <strong>ORBITAL Operator Review UI</strong>
      <span>Local read-only review surface for evidence bundles</span>
    </header>
    <main>
      <section class="hero" aria-label="Operator review dashboard">
        <div class="verdict">
          <span class="eyebrow">{escape(_text(mission_name))}</span>
          <h1>Mission Verdict: <span class="verdict-badge {_status_class(verdict["label"])}">{escape(verdict["label"])}</span></h1>
          <p>{escape(verdict["meaning"])}</p>
          <div class="next-action">
            <strong>Next operator action</strong>
            <p>{escape(verdict["next_action"])}</p>
          </div>
          <div class="signals" aria-label="Mission signals">
            {cards}
          </div>
        </div>
        <aside class="side-stack" aria-label="Product boundary and bundle artifacts">
          <section class="panel">
            <h2>Product Boundary</h2>
            <ul class="boundary-list">
              <li>This UI is a local review surface for ORBITAL evidence bundles.</li>
              <li>ORBITAL remains decision support, not approval, authorization, LAANC, legal advice, or operational clearance.</li>
              <li>Opening, clicking, or reviewing an artifact does not approve a mission.</li>
              <li>Review fields are documentation-only records.</li>
              <li>Markdown, JSON, CSV, KML, and checksum artifacts remain accessible outside this UI.</li>
            </ul>
          </section>
          {_route_preview(manifest)}
          <section class="panel">
            <h2>Source Artifacts</h2>
            <div class="quick-links">
              {_artifact_link(manifest, ("operator_dashboard",), "Dashboard MD")}
              {_artifact_link(manifest, ("constraint_audit_markdown",), "Constraint Audit")}
              {_artifact_link(manifest, ("manifest_json",), "Manifest JSON")}
              {_artifact_link(manifest, ("checksum_manifest",), "Checksums")}
            </div>
          </section>
          <section class="panel">
            <h2>Review Metadata</h2>
            <div class="meta-grid">
              <div><span>Status</span><strong>{escape(_text(review.get("status")).replace("_", " "))}</strong></div>
              <div><span>Decision</span><strong>{escape(_text(review.get("operator_decision"), "pending operator review"))}</strong></div>
              <div><span>Reviewer</span><strong>{escape(_text(review.get("reviewer_name")))}</strong></div>
              <div><span>Timestamp</span><strong>{escape(_text(review.get("review_timestamp_utc")))}</strong></div>
            </div>
          </section>
        </aside>
      </section>
    </main>
  </div>
</body>
</html>
"""
    return html
