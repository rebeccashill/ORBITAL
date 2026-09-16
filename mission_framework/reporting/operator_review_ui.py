from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

from mission_framework.reporting.operator_review_ui_scripts import (
    operator_review_manifest_loader_script,
)
from mission_framework.reporting.operator_review_ui_styles import operator_review_ui_css

_ARTIFACT_DEFINITIONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("operator_dashboard",), "operator_dashboard.md"),
    (("constraint_audit_markdown",), "inspection_constraint_audit.md"),
    (("what_if_plan_markdown",), "what_if_plan.md"),
    (("regulatory_readiness_markdown",), "regulatory_readiness_report.md"),
    (("bundle_summary",), "evidence_bundle_summary.md"),
    (("artifact_index",), "artifact_index.md"),
    (("manifest_json",), "manifest.json"),
    (("checksum_manifest",), "checksum_manifest.json"),
    (("flight_path_plot",), "flight_path.png"),
    (("autopilot_mission_csv",), "autopilot_mission.csv"),
    (("mission_review_kml",), "mission_review.kml"),
)

_RAW_EVIDENCE_GROUPS: tuple[tuple[str, tuple[tuple[tuple[str, ...], str], ...]], ...] = (
    (
        "Raw Markdown",
        (
            (("operator_dashboard",), "operator_dashboard.md"),
            (("constraint_audit_markdown",), "inspection_constraint_audit.md"),
            (("what_if_plan_markdown",), "what_if_plan.md"),
            (("regulatory_readiness_markdown",), "regulatory_readiness_report.md"),
            (("bundle_summary",), "evidence_bundle_summary.md"),
            (("artifact_index",), "artifact_index.md"),
        ),
    ),
    (
        "JSON Evidence",
        (
            (("plan_json",), "plan.json"),
            (("constraint_audit_json",), "inspection_constraint_audit.json"),
            (("what_if_plan_json",), "what_if_plan.json"),
            (("regulatory_readiness_json",), "regulatory_readiness_report.json"),
            (("score_breakdown",), "score_breakdown.json"),
            (("weather_snapshot",), "weather_snapshot.json"),
            (("robustness_summary",), "robustness_summary.json"),
        ),
    ),
    (
        "CSV / KML",
        (
            (("autopilot_mission_csv",), "autopilot_mission.csv"),
            (("mission_review_kml",), "mission_review.kml"),
        ),
    ),
    (
        "Plots",
        ((("flight_path_plot",), "flight_path.png"),),
    ),
    (
        "Manifest / checksum",
        (
            (("manifest_json",), "manifest.json"),
            (("checksum_manifest",), "checksum_manifest.json"),
        ),
    ),
)


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    if normalized in {
        "go",
        "pass",
        "clear",
        "ready",
        "ready_for_review",
        "configured_source",
        "documented",
        "fresh",
        "live",
        "low",
    }:
        return "status-good"
    if normalized in {
        "review",
        "review_required",
        "operator_action_required",
        "warning",
        "fallback_used",
        "packaged",
        "pending_operator_confirmation",
        "sample",
        "stale",
        "verify_required",
        "not_run",
        "medium",
        "moderate",
    }:
        return "status-review"
    if normalized in {"modify", "fail", "failed", "elevated_risk", "expired", "missing", "high"}:
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


def _verdict_derivation(
    *,
    verdict: Mapping[str, Any],
    mission_status: str,
    regulatory_state: str,
    missing_evidence_count: int,
    warning_count: int,
) -> dict[str, Any]:
    mission_key = mission_status.replace(" ", "_")
    regulatory_key = regulatory_state.replace(" ", "_")
    if mission_key != "GO":
        explanation = "The verdict is MODIFY because the modeled mission status is not GO."
    elif (
        regulatory_key == "OPERATOR_ACTION_REQUIRED"
        or missing_evidence_count > 0
        or warning_count > 0
    ):
        explanation = (
            "The verdict is REVIEW REQUIRED because modeled feasibility is GO but "
            "regulatory readiness, missing evidence, or bundle warnings still need "
            "operator attention."
        )
    else:
        explanation = (
            "The verdict is GO because modeled mission status is GO, regulatory "
            "readiness does not require action, and no missing evidence or bundle "
            "warnings are recorded."
        )
    return {
        "label": verdict.get("label"),
        "explanation": explanation,
        "inputs": [
            {
                "signal": "Modeled mission status",
                "value": mission_status,
                "effect": "MODIFY if not GO.",
            },
            {
                "signal": "Regulatory readiness",
                "value": regulatory_state,
                "effect": "REVIEW REQUIRED when OPERATOR_ACTION_REQUIRED.",
            },
            {
                "signal": "Missing evidence",
                "value": f"{missing_evidence_count} item(s)",
                "effect": "REVIEW REQUIRED when greater than 0.",
            },
            {
                "signal": "Bundle warnings",
                "value": f"{warning_count} warning(s)",
                "effect": "REVIEW REQUIRED when greater than 0.",
            },
        ],
    }


def _warning_kind_count(warnings: Sequence[Mapping[str, Any]], *kinds: str) -> int:
    wanted = set(kinds)
    return sum(1 for warning in warnings if warning.get("kind") in wanted)


def _mismatch_warning_count(
    evidence_warnings: Mapping[str, Any],
    bundle_warnings: Sequence[Mapping[str, Any]],
) -> int:
    explicit_count = evidence_warnings.get("mismatched_artifacts")
    if explicit_count is not None:
        return _int(explicit_count)
    return sum(
        1 for warning in bundle_warnings if "mismatch" in _text(warning.get("kind"), "").lower()
    )


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


def _artifact_kind(label: str) -> str:
    suffix = Path(label).suffix.strip(".").upper()
    return suffix if suffix else "FILE"


def _slug(value: str) -> str:
    rendered = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            rendered.append(char)
            previous_dash = False
        elif not previous_dash:
            rendered.append("-")
            previous_dash = True
    slug = "".join(rendered).strip("-")
    return slug or "section"


def _artifact_link(manifest: Mapping[str, Any], ids: Sequence[str], label: str) -> str:
    entry = _artifact_entry(manifest, ids)
    kind = escape(_artifact_kind(label))
    if entry and entry.get("present") and entry.get("bundle_path"):
        aria_label = escape(f"Open {label}", quote=True)
        return (
            f'<a class="artifact-link" href="{_href(entry.get("bundle_path"))}" '
            f'aria-label="{aria_label}">'
            f"<span>{escape(label)}</span><small>{kind}</small></a>"
        )
    return (
        '<span class="artifact-link artifact-unavailable unavailable">'
        f"<span>{escape(label)} unavailable</span><small>Missing</small></span>"
    )


def _open_first(manifest: Mapping[str, Any]) -> str:
    return (
        '<div class="open-first" data-open-first aria-label="First artifact to open">'
        "<span>Open first: first artifact to open</span>"
        f"{_artifact_link(manifest, ('operator_dashboard',), 'operator_dashboard.md')}"
        "<p>Start here for the verdict, next action, and 30-second mission read. "
        "This is the primary review surface before opening supporting artifacts.</p>"
        "</div>"
    )


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


def _read_item(
    label: str,
    value: Any,
    detail: str = "",
    class_name: str = "",
    *,
    field: str = "",
    wide: bool = False,
) -> str:
    css_parts = ["read-item"]
    if class_name:
        css_parts.append(class_name)
    if wide:
        css_parts.append("read-action")
    field_attr = f' data-field="{escape(field, quote=True)}"' if field else ""
    detail_html = f"<p>{escape(detail)}</p>" if detail else ""
    return (
        f'<article class="{" ".join(css_parts)}">'
        f"<span>{escape(label)}</span>"
        f"<strong{field_attr}>{escape(_text(value))}</strong>"
        f"{detail_html}"
        "</article>"
    )


def _short_text(value: Any, default: str = "not provided", limit: int = 170) -> str:
    text = _text(value, default)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _kv(label: str, value: Any, class_name: str = "") -> str:
    css = f' class="{class_name}"' if class_name else ""
    return (
        "<div>"
        f"<span>{escape(label)}</span>"
        f"<strong{css}>{escape(_text(value))}</strong>"
        "</div>"
    )


def _micro_kv(label: str, value: Any, class_name: str = "") -> str:
    css = (
        f' class="evidence-detail-row {class_name}"'
        if class_name
        else ' class="evidence-detail-row"'
    )
    return (
        f"<div{css}>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(_text(value))}</strong>"
        "</div>"
    )


def _compact_list(items: Sequence[Any], *, empty: str = "none", limit: int = 3) -> str:
    if not items:
        return f"<li>{escape(empty)}</li>"
    rendered = []
    for item in items[:limit]:
        if isinstance(item, Mapping):
            label = item.get("label") or item.get("id") or item.get("kind") or "item"
            detail = item.get("note") or item.get("message") or item.get("path")
            text = f"{label}: {detail}" if detail else label
        else:
            text = item
        rendered.append(f"<li>{escape(_short_text(text, limit=150))}</li>")
    remaining = len(items) - limit
    if remaining > 0:
        rendered.append(f"<li>{remaining} more in the source artifact</li>")
    return "\n".join(rendered)


def _model_assumptions_preview(trust: Mapping[str, Any], *, limit: int = 3) -> str:
    assumptions = list(trust.get("model_assumptions_summary", []) or [])
    if not assumptions:
        return (
            '<p class="compact-note">No model assumptions were captured. Operator should '
            "verify scenario inputs in the constraint audit.</p>"
        )
    items = []
    for item in assumptions[:limit]:
        label = _text(item.get("label") or item.get("id"), "Model assumption")
        assumption = _short_text(item.get("assumption"), "not provided", 120)
        operator_note = _short_text(
            item.get("operator_review_note"),
            "Operator should verify this assumption before release.",
            110,
        )
        items.append(
            "<li>"
            f"<strong>{escape(label)}</strong>"
            f"<span>{escape(assumption)}</span>"
            f"<em>{escape(operator_note)}</em>"
            "</li>"
        )
    return '<ul class="assumption-list">' + "\n".join(items) + "</ul>"


def _artifact_freshness_preview(manifest: Mapping[str, Any], *, limit: int = 5) -> str:
    priority = {
        "scenario_yaml": 0,
        "constraint_audit_markdown": 1,
        "regulatory_readiness_markdown": 2,
        "what_if_plan_markdown": 3,
        "weather_snapshot": 4,
        "autopilot_mission_csv": 5,
        "mission_review_kml": 6,
    }
    entries = sorted(
        list(manifest.get("artifacts", []) or []),
        key=lambda item: (
            priority.get(str(item.get("id")), 99),
            str(item.get("label") or item.get("id") or ""),
        ),
    )
    rows = []
    for entry in entries[:limit]:
        freshness = entry.get("freshness") if isinstance(entry.get("freshness"), Mapping) else {}
        present = bool(entry.get("present"))
        stale = bool(freshness.get("stale_against_scenario"))
        if not present:
            status = "MISSING"
        elif stale:
            status = "STALE"
        else:
            status = "CURRENT"
        rows.append(
            "<div>"
            f"<span>{escape(_text(entry.get('label') or entry.get('id'), 'Artifact'))}</span>"
            f'<strong class="{_status_class(status)}">{escape(status)}</strong>'
            f"<small>source {escape(_text(freshness.get('source_modified_utc')))}</small>"
            f"<small>bundle {escape(_text(freshness.get('bundle_modified_utc')))}</small>"
            "</div>"
        )
    if not rows:
        return '<p class="compact-note">No artifact freshness metadata captured.</p>'
    return '<div class="freshness-list">' + "\n".join(rows) + "</div>"


def _compatibility(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    return _as_mapping(manifest.get("ui_compatibility"))


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _freshness_checksum_strip(manifest: Mapping[str, Any]) -> str:
    freshness = _as_mapping(manifest.get("freshness"))
    checksum = _as_mapping(manifest.get("checksum_evidence_readiness"))
    compatibility = _compatibility(manifest)
    manifest_version = (
        manifest.get("manifest_version")
        or manifest.get("ui_manifest_version")
        or compatibility.get("manifest_version")
    )
    checksum_status = _status_label(checksum.get("status"))
    return (
        '<section class="freshness-strip" aria-label="Manifest, checksum, and freshness status">'
        "<article>"
        "<span>Manifest version</span>"
        f'<strong data-field="manifest-version">{escape(_text(manifest_version, "legacy / not provided"))}</strong>'
        f"<small>UI schema {escape(_text(compatibility.get('schema_version')))}</small>"
        "</article>"
        "<article>"
        "<span>Generated</span>"
        f'<strong data-field="generated-timestamp">{escape(_text(freshness.get("generated_timestamp_utc")))}</strong>'
        f"<small>scenario {escape(_text(freshness.get('scenario_modified_utc')))}</small>"
        "</article>"
        "<article>"
        "<span>Checksum</span>"
        f'<strong class="{_status_class(checksum_status)}" data-field="checksum-status">{escape(checksum_status)}</strong>'
        f"<small>{escape(_short_text(checksum.get('operator_action'), 'Run bundle checksum verification before archiving.', 110))}</small>"
        "</article>"
        "</section>"
    )


def _manifest_compatibility_panel(manifest: Mapping[str, Any]) -> str:
    compatibility = _compatibility(manifest)
    artifact_access = _as_mapping(compatibility.get("artifact_access"))
    required_fields = list(compatibility.get("required_top_level_fields") or [])
    fallback_count = len(compatibility.get("optional_field_fallbacks") or {})
    expected_formats = ", ".join(artifact_access.get("expected_formats") or []) or (
        "Markdown, JSON, CSV, KML, PNG, manifest, checksum, dashboard"
    )
    return (
        "<div data-ui-compatibility>"
        '<div class="meta-grid">'
        f"{_kv('Manifest version', manifest.get('manifest_version') or compatibility.get('manifest_version'), _status_class('documented'))}"
        f"{_kv('UI schema', compatibility.get('schema_version'))}"
        f"{_kv('Required UI fields', f'{len(required_fields)} expected')}"
        f"{_kv('Fallback fields', f'{fallback_count} documented')}"
        "</div>"
        f'<p class="compact-note">{escape(_text(compatibility.get("optional_field_fallback_policy"), "Optional UI fields use explicit fallback text."))}</p>'
        f'<p class="compact-note">Outside-UI access: {escape(expected_formats)}.</p>'
        f'<p class="compact-note">{escape(_text(artifact_access.get("unavailable_artifact_policy"), "Unavailable artifacts render as non-link unavailable labels."))}</p>'
        "</div>"
    )


def _trust_status_summary(
    *,
    mission_status: str,
    regulatory_state: str,
    regulatory_provenance_status: str,
    missing_count: int,
    warning_count: int,
    stale_missing_mismatch_count: int,
    weather_status: str,
    checksum_status: str,
) -> dict[str, str]:
    mission_key = mission_status.replace(" ", "_")
    if mission_key != "GO":
        return {
            "label": "Model changes needed first",
            "detail": f"Modeled status is {mission_status}; revise the mission before release review.",
            "status": mission_status,
        }

    cues = []
    regulatory_key = regulatory_state.replace(" ", "_")
    provenance_key = regulatory_provenance_status.replace(" ", "_")
    if regulatory_key == "OPERATOR_ACTION_REQUIRED" or provenance_key in {
        "STALE",
        "PENDING_OPERATOR_CONFIRMATION",
        "VERIFY_REQUIRED",
        "EXPIRED",
    }:
        cues.append("regulatory confirmation")
    weather_key = weather_status.replace(" ", "_")
    checksum_key = checksum_status.replace(" ", "_")
    if weather_key in {"STALE", "FALLBACK_USED", "SAMPLE", "UNKNOWN"}:
        cues.append("weather evidence check")
    if missing_count > 0:
        cues.append(f"{missing_count} missing evidence item(s)")
    if warning_count > 0:
        cues.append(f"{warning_count} evidence warning(s)")
    if stale_missing_mismatch_count > 0:
        cues.append(f"{stale_missing_mismatch_count} stale/missing/mismatched artifact(s)")
    if checksum_key in {"VERIFY_REQUIRED", "NOT_RUN", "UNKNOWN"}:
        cues.append("checksum verification")

    if cues:
        return {
            "label": "Operator trust review needed",
            "detail": f"Check {', '.join(cues[:4])}.",
            "status": "review_required",
        }
    return {
        "label": "Trust signals clear",
        "detail": "No missing evidence, bundle warnings, or trust checks are flagged.",
        "status": "clear",
    }


def _thirty_second_read(
    *,
    verdict: Mapping[str, str],
    top_summary: str,
    trust_status: Mapping[str, str],
) -> str:
    return (
        '<section class="thirty-second-read" data-thirty-second-read '
        'aria-label="30-second mission read">'
        "<header>"
        "<span>30-Second Mission Read</span>"
        "<strong>Verdict, limiter, trust posture, action.</strong>"
        "</header>"
        '<div class="read-grid">'
        f"{_read_item('Verdict', verdict.get('label'), verdict.get('meaning', ''), _status_class(verdict.get('label')))}"
        f"{_read_item('Top constraint', top_summary, 'Most likely to limit release.', 'signal-top')}"
        f"{_read_item('Trust status', trust_status.get('label'), trust_status.get('detail', ''), _status_class(trust_status.get('status')))}"
        f"{_read_item('Next operator action', verdict.get('next_action'), 'Before field release, operator authority stays outside ORBITAL.', _status_class(verdict.get('label')), field='next-action', wide=True)}"
        "</div>"
        "</section>"
    )


def _next_action_panel(verdict: Mapping[str, str]) -> str:
    return (
        '<section class="next-action" aria-label="Next operator action">'
        "<strong>Next operator action</strong>"
        f'<p data-field="next-action">{escape(_text(verdict.get("next_action")))}</p>'
        "</section>"
    )


def _source_links(manifest: Mapping[str, Any]) -> str:
    links = [_artifact_link(manifest, ids, label) for ids, label in _ARTIFACT_DEFINITIONS]
    return "\n".join(links)


def _raw_evidence_quick_links(manifest: Mapping[str, Any]) -> str:
    groups = []
    for title, definitions in _RAW_EVIDENCE_GROUPS:
        links = "\n".join(_artifact_link(manifest, ids, label) for ids, label in definitions)
        groups.append(
            '<section class="quick-link-group">'
            f"<h3>{escape(title)}</h3>"
            f'<div class="quick-links">{links}</div>'
            "</section>"
        )
    return "\n".join(groups)


def _review_order_strip(top_summary: str) -> str:
    steps = [
        ("Verdict", "mission-verdict", "Mission verdict and next operator action"),
        ("Top constraint", "feasibility", top_summary),
        ("Trust signals", "trust-defensibility", "Readiness, assumptions, and warnings"),
        ("Artifacts", "source-artifacts", "Open the first artifact, then raw evidence"),
        ("Checksum", "checksum-review", "Verify manifest and checksum evidence"),
    ]
    items = []
    for index, (label, target, detail) in enumerate(steps, start=1):
        items.append(
            "<li>"
            f'<a href="#{escape(target, quote=True)}">'
            f"<span>{index}</span>"
            f"<strong>{escape(label)}</strong>"
            f"<small>{escape(_short_text(detail, limit=92))}</small>"
            "</a>"
            "</li>"
        )
    return (
        '<nav class="review-order" aria-label="Review order">'
        "<span>Review Order</span>"
        "<p>Verdict -> top constraint -> trust signals -> artifacts -> checksum</p>"
        f"<ol>{''.join(items)}</ol>"
        "</nav>"
    )


def _review_section(
    title: str,
    summary: str,
    body_html: str,
    links_html: str = "",
    section_id: str = "",
) -> str:
    links = f'<div class="section-links">{links_html}</div>' if links_html else ""
    section_slug = section_id or _slug(title)
    heading_id = f"{section_slug}-heading"
    return (
        f'<article class="review-section" id="{escape(section_slug, quote=True)}" '
        'tabindex="0" '
        f'aria-labelledby="{escape(heading_id, quote=True)}">'
        f'<h2 id="{escape(heading_id, quote=True)}">{escape(title)}</h2>'
        f"<p>{escape(summary)}</p>"
        f"{body_html}"
        f"{links}"
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


def _review_sections(
    *,
    manifest: Mapping[str, Any],
    mission_status: str,
    mission_risk: str,
    regulatory_state: str,
    top_summary: str,
    evidence_completeness: str,
    regulatory_doc_completeness: str,
    weather_status: str,
    weather_summary: str,
    robustness_status: str,
    robustness_summary: str,
    evidence_warning_summary: str,
    missing_count: int,
    warning_count: int,
    stale_count: int,
    missing_artifact_count: int,
    mismatch_count: int,
) -> str:
    review = manifest.get("operator_review") or {}
    regulatory_status = manifest.get("regulatory_evidence_status") or {}
    approval_checklist = manifest.get("approval_checklist") or {}
    trust = manifest.get("trust_defensibility") or {}
    weather_readiness = (
        manifest.get("weather_evidence_readiness")
        or trust.get("weather_evidence_readiness")
        or trust.get("weather_fallback_status")
        or {}
    )
    regulatory_provenance = (
        manifest.get("regulatory_evidence_provenance")
        or trust.get("regulatory_evidence_provenance")
        or {}
    )
    checksum_readiness = manifest.get("checksum_evidence_readiness") or {}
    bundle_completeness = (
        manifest.get("bundle_completeness") or manifest.get("artifact_completeness") or {}
    )
    sample_note = trust.get("sample_data_demo_note") or {}
    missing_evidence = manifest.get("missing_evidence") or []
    bundle_warnings = manifest.get("bundle_warnings") or []
    pending_count = approval_checklist.get("pending_count", approval_checklist.get("item_count", 0))
    missing_regulatory = regulatory_status.get("missing", []) or []

    feasibility_body = (
        '<div class="compact-grid">'
        f"{_kv('Modeled status', mission_status, _status_class(mission_status))}"
        f"{_kv('Mission risk', mission_risk, _status_class(mission_risk))}"
        f"{_kv('Top constraint', top_summary)}"
        "</div>"
    )
    regulatory_body = (
        '<div class="compact-grid">'
        f"{_kv('Readiness', regulatory_state, _status_class(regulatory_state))}"
        f"{_kv('Documentation', regulatory_doc_completeness)}"
        f"{_kv('Checklist pending', pending_count)}"
        f"{_kv('Missing fields', len(missing_regulatory))}"
        "</div>"
    )
    live_evidence_body = (
        '<div class="compact-grid evidence-readiness-grid">'
        f"{_kv('Weather status', _status_label(weather_readiness.get('status')), _status_class(weather_readiness.get('status')))}"
        f"{_kv('Regulatory provenance', _status_label(regulatory_provenance.get('status')), _status_class(regulatory_provenance.get('status')))}"
        f"{_kv('Checksum evidence', _status_label(checksum_readiness.get('status')), _status_class(checksum_readiness.get('status')))}"
        "</div>"
        '<details class="evidence-disclosure">'
        "<summary>Source, freshness, and provenance details</summary>"
        '<div class="evidence-detail-grid">'
        f"{_micro_kv('Weather source', weather_readiness.get('source'))}"
        f"{_micro_kv('Weather timestamp', weather_readiness.get('timestamp_utc'))}"
        f"{_micro_kv('Weather freshness', weather_readiness.get('freshness_status'))}"
        f"{_micro_kv('Authority', regulatory_provenance.get('authority'))}"
        f"{_micro_kv('Date checked', regulatory_provenance.get('date_checked_utc'))}"
        f"{_micro_kv('Expiration', regulatory_provenance.get('expiration_date'))}"
        f"{_micro_kv('Operator confirmation', regulatory_provenance.get('operator_confirmation_status'))}"
        f"{_micro_kv('Weather action', _short_text(weather_readiness.get('operator_action'), limit=110), 'wide')}"
        "</div>"
        "</details>"
        '<p class="compact-note">Live weather and regulatory hooks are documentation-only unless verified outside ORBITAL.</p>'
    )
    artifacts_present = (
        f"{_int(bundle_completeness.get('present_artifacts'))} / "
        f"{_int(bundle_completeness.get('total_artifacts'))}"
    )
    completeness_body = (
        '<div class="compact-grid completeness-grid">'
        f"{_kv('Artifact coverage', _pct(bundle_completeness.get('score')))}"
        f"{_kv('Artifacts present', artifacts_present)}"
        f"{_kv('Missing evidence', missing_count)}"
        f"{_kv('Bundle warnings', warning_count)}"
        "</div>"
    )
    trust_body = (
        '<div class="compact-grid">'
        f"{_kv('Weather evidence', weather_status, _status_class(weather_status))}"
        f"{_kv('Robustness', robustness_status, _status_class(robustness_status))}"
        "</div>"
        '<details class="evidence-disclosure">'
        "<summary>Weather, robustness, and sample-data notes</summary>"
        '<div class="evidence-detail-grid">'
        f"{_micro_kv('Weather note', _short_text(weather_summary), 'wide')}"
        f"{_micro_kv('Robustness note', _short_text(robustness_summary), 'wide')}"
        f"{_micro_kv('Sample note', _short_text(sample_note.get('note'), 'Verify scenario inputs before operational use.'), 'wide')}"
        "</div>"
        "</details>"
    )
    warnings_body = (
        '<div class="compact-grid">'
        f"{_kv('Stale artifacts', stale_count)}"
        f"{_kv('Missing artifacts', missing_artifact_count)}"
        f"{_kv('Mismatched artifacts', mismatch_count)}"
        f"{_kv('Warning total', warning_count, _status_class('clear' if warning_count == 0 else 'review_required'))}"
        "</div>"
        '<details class="evidence-disclosure">'
        "<summary>Warning details</summary>"
        f'<p class="compact-note">{escape(evidence_warning_summary)}</p>'
        f'<ul class="compact-list">{_compact_list(bundle_warnings or missing_evidence, empty="No bundle warnings captured.")}</ul>'
        "</details>"
    )
    data_loading_body = (
        '<div class="meta-grid">'
        "<div><span>Primary source</span><strong>outputs/bvlos_powerline_inspection/operator_evidence_bundle/manifest.json</strong></div>"
        "<div><span>Runtime target</span><strong>manifest.json</strong></div>"
        "<div><span>Writes</span><strong>read-only UI; no bundle mutation</strong></div>"
        "<div><span>Storage</span><strong>no backend database required</strong></div>"
        "</div>"
        '<p class="loading-status status-neutral" data-manifest-status>Preparing review data from embedded snapshot or manifest.json...</p>'
    )
    artifact_body = '<p class="compact-note">Open source artifacts directly; this page summarizes them without replacing Markdown, JSON, CSV, KML, or checksum files.</p>'
    metadata_body = (
        '<div class="compact-grid">'
        f"{_kv('Status', _text(review.get('status')).replace('_', ' '))}"
        f"{_kv('Decision', _text(review.get('operator_decision'), 'pending operator review'))}"
        f"{_kv('Reviewer', _text(review.get('reviewer_name')))}"
        f"{_kv('Timestamp', _text(review.get('review_timestamp_utc')))}"
        "</div>"
        '<p class="compact-note">Review metadata is documentation-only and does not change release authority.</p>'
    )

    sections = [
        _review_section(
            "Feasibility",
            "Modeled mission feasibility and the constraint most likely to limit release.",
            feasibility_body,
            _artifact_link(manifest, ("constraint_audit_markdown",), "Constraint audit"),
            "feasibility",
        ),
        _review_section(
            "Regulatory Readiness",
            "Documentation-only readiness signals for operator confirmation outside ORBITAL.",
            regulatory_body,
            _artifact_link(manifest, ("regulatory_readiness_markdown",), "Regulatory report"),
            "regulatory-readiness",
        ),
        _review_section(
            "Weather / Live Evidence",
            "Source, freshness, provenance, and operator-action hooks for operational evidence review.",
            live_evidence_body,
            "\n".join(
                [
                    _artifact_link(manifest, ("weather_snapshot",), "Weather snapshot"),
                    _artifact_link(
                        manifest, ("regulatory_readiness_markdown",), "Regulatory report"
                    ),
                ]
            ),
            "live-evidence-readiness",
        ),
        _review_section(
            "Evidence Completeness",
            "Expected bundle artifacts and missing evidence counts.",
            completeness_body,
            "\n".join(
                [
                    _artifact_link(manifest, ("manifest_json",), "Manifest"),
                    _artifact_link(manifest, ("checksum_manifest",), "Checksums"),
                ]
            ),
            "evidence-completeness",
        ),
        _review_section(
            "Trust / Defensibility",
            "Weather evidence, uncertainty, and model-context signals for audit review.",
            trust_body,
            _artifact_link(manifest, ("operator_dashboard",), "Dashboard MD"),
            "trust-defensibility",
        ),
        _review_section(
            "Warnings",
            "Stale, missing, mismatched, or otherwise review-required evidence signals.",
            warnings_body,
            _artifact_link(manifest, ("checksum_manifest",), "Checksum manifest"),
            "warnings",
        ),
        _review_section(
            "Data Loading",
            "Manifest load path and runtime read-only status.",
            data_loading_body,
            section_id="data-loading",
        ),
        _review_section(
            "Artifact Navigation",
            "Shortcuts to the underlying source-of-truth bundle files.",
            _open_first(manifest) + artifact_body,
            _source_links(manifest),
            "artifact-navigation",
        ),
        _review_section(
            "Operator Review Metadata",
            "Current review-state fields captured for documentation only.",
            metadata_body,
            section_id="operator-review-metadata",
        ),
    ]
    return (
        '<div class="review-intro-row">'
        f"{sections[0]}\n{sections[1]}"
        "</div>"
        '<div class="review-column-grid">'
        '<div class="review-column">'
        f"{sections[2]}\n{sections[6]}\n{sections[8]}"
        "</div>"
        '<div class="review-column">'
        f"{sections[3]}\n{sections[4]}\n{sections[5]}\n{sections[7]}"
        "</div>"
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
    weather_readiness = (
        manifest.get("weather_evidence_readiness")
        or trust.get("weather_evidence_readiness")
        or weather
    )
    robustness = trust.get("uncertainty_robustness_status") or {}
    evidence_warnings = trust.get("evidence_warning_summary") or {}
    missing_evidence = manifest.get("missing_evidence") or []
    bundle_warnings = manifest.get("bundle_warnings") or []
    review = manifest.get("operator_review") or {}
    checksum_readiness = manifest.get("checksum_evidence_readiness") or {}

    mission_status = _status_label(audit.get("status"))
    mission_risk = _status_label(audit.get("mission_risk"))
    regulatory_state = _status_label(readiness.get("readiness_state") or readiness.get("status"))
    warning_count = _int(evidence_warnings.get("bundle_warnings", len(bundle_warnings)))
    missing_count = _int(evidence_warnings.get("missing_evidence", len(missing_evidence)))
    stale_count = _int(
        evidence_warnings.get(
            "stale_artifacts",
            _warning_kind_count(bundle_warnings, "stale_artifact"),
        )
    )
    missing_artifact_count = _int(
        evidence_warnings.get(
            "missing_artifacts",
            _warning_kind_count(bundle_warnings, "missing_artifact"),
        )
    )
    mismatch_count = _mismatch_warning_count(evidence_warnings, bundle_warnings)
    verdict = _dashboard_verdict(
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        missing_evidence_count=missing_count,
        warning_count=warning_count,
    )
    verdict_derivation = _verdict_derivation(
        verdict=verdict,
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        missing_evidence_count=missing_count,
        warning_count=warning_count,
    )
    verdict_derivation_items = "".join(
        _kv(
            str(item.get("signal")),
            f"{item.get('value')} - {item.get('effect')}",
            _status_class(item.get("value")),
        )
        for item in verdict_derivation["inputs"]
    )
    mission_name = (
        audit.get("mission_id") or Path(_text(manifest.get("scenario_path"), "scenario")).stem
    )
    top_summary = _margin_summary(audit.get("top_limiting_constraint") or {})
    evidence_completeness = _counted_score(completeness, total_label="artifacts")
    regulatory_doc_completeness = _counted_score(regulatory_completeness, total_label="fields")
    weather_status = _status_label(weather_readiness.get("status") or weather.get("status"))
    weather_summary = _text(
        weather_readiness.get("summary") or weather.get("summary"),
        "No weather evidence status captured.",
    )
    robustness_status = _status_label(robustness.get("status"))
    robustness_summary = _text(
        robustness.get("summary"), "No robustness / uncertainty status captured."
    )
    checksum_action = _text(
        checksum_readiness.get("operator_action"),
        "Run bundle checksum verification before archiving or sharing the evidence bundle.",
    )
    evidence_warning_summary = _text(
        evidence_warnings.get("summary"),
        f"{missing_artifact_count} missing artifact(s), {stale_count} stale artifact(s), "
        f"{missing_count} missing evidence item(s), {warning_count} bundle warning(s)",
    )
    review_sections = _review_sections(
        manifest=manifest,
        mission_status=mission_status,
        mission_risk=mission_risk,
        regulatory_state=regulatory_state,
        top_summary=top_summary,
        evidence_completeness=evidence_completeness,
        regulatory_doc_completeness=regulatory_doc_completeness,
        weather_status=weather_status,
        weather_summary=weather_summary,
        robustness_status=robustness_status,
        robustness_summary=robustness_summary,
        evidence_warning_summary=evidence_warning_summary,
        missing_count=missing_count,
        warning_count=warning_count,
        stale_count=stale_count,
        missing_artifact_count=missing_artifact_count,
        mismatch_count=mismatch_count,
    )
    loader_script = operator_review_manifest_loader_script(manifest)

    cards = "\n".join(
        [
            _stat_card(
                "Modeled mission status",
                mission_status,
                class_name=f"decision-signal {_status_class(mission_status)}",
            ),
            _stat_card(
                "Mission risk",
                mission_risk,
                class_name=f"decision-signal {_status_class(mission_risk)}",
            ),
            _stat_card(
                "Top limiting constraint", top_summary, class_name="decision-signal signal-top"
            ),
            _stat_card(
                "Regulatory readiness",
                regulatory_state,
                class_name=f"decision-signal {_status_class(regulatory_state)}",
            ),
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ORBITAL Operator Review</title>
  <link rel="icon" href="data:,">
  <style>
{operator_review_ui_css()}
  </style>
</head>
<body>
  <a class="skip-link" href="#review-sections">Skip to review sections</a>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div>
          <strong>ORBITAL Operator Review UI</strong>
          <span>Local read-only review surface for evidence bundles</span>
        </div>
        <div class="topbar-actions">
          <button class="print-button" type="button" onclick="window.print()">Print / demo view</button>
          <span class="read-only-pill">Read-only demo / discovery aid</span>
        </div>
      </div>
    </header>
    <main>
      <section class="dashboard-grid" aria-label="Operator review dashboard">
        <div class="dashboard-left">
          <div class="dashboard-primary">
            <div class="review-lead">
              <section class="verdict-band" id="mission-verdict" aria-label="Mission verdict">
                <span class="eyebrow" data-field="mission-name">{escape(_text(mission_name))}</span>
                <h1>Mission Verdict: <span class="verdict-badge {_status_class(verdict["label"])}" data-field="verdict-label">{escape(verdict["label"])}</span></h1>
                <p data-field="verdict-meaning">{escape(verdict["meaning"])}</p>
                <p class="boundary-callout">Decision support only; the generated evidence bundle remains the source of truth.</p>
              </section>
              {_next_action_panel(verdict)}
            </div>
            <div class="priority-stack dashboard-context" aria-label="Immediate review context">
              {_freshness_checksum_strip(manifest)}
              {_review_order_strip(top_summary)}
              <section class="panel why-verdict" data-why-verdict>
                <h2>Why This Verdict?</h2>
                <p>{escape(_text(verdict_derivation.get("explanation")))}</p>
                <div class="compact-grid">
                  {verdict_derivation_items}
                </div>
              </section>
            </div>
            <div class="signals" aria-label="Mission signals" data-signals>
              {cards}
            </div>
          </div>
          <section class="supporting-evidence" aria-label="Supporting evidence and artifacts">
            <section class="review-sections dashboard-review-sections" id="review-sections" aria-label="Compact review sections" data-review-sections>
              {review_sections}
            </section>
          </section>
        </div>
        <aside class="dashboard-sidebar" aria-label="Product boundary and manifest context">
          <section class="panel product-boundary-panel">
            <h2>Product Boundary</h2>
            <ul class="boundary-list">
              <li>This UI is a local review surface for ORBITAL evidence bundles.</li>
              <li>It is a demo and discovery aid, not a full SaaS product.</li>
              <li>ORBITAL remains decision support, not approval, authorization, LAANC, legal advice, or operational clearance.</li>
              <li>Opening, clicking, or reviewing an artifact does not approve a mission.</li>
              <li>Review fields are documentation-only records.</li>
              <li>No accounts, databases, auth, editing workflows, live integrations, approvals, or signoff actions are provided.</li>
              <li>Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts remain accessible outside this UI.</li>
            </ul>
          </section>
          <section class="panel" id="manifest-compatibility">
            <h2>Manifest Compatibility</h2>
            {_manifest_compatibility_panel(manifest)}
          </section>
          <section class="panel" data-model-assumptions>
            <h2>Model Assumptions</h2>
            {_model_assumptions_preview(trust)}
          </section>
          <aside class="side-stack" aria-label="Bundle artifacts and evidence navigation">
            {_route_preview(manifest)}
            <section class="panel" data-artifact-freshness>
              <h2>Artifact Freshness</h2>
              {_artifact_freshness_preview(manifest)}
            </section>
            <section class="panel" id="source-artifacts">
              <h2>Source Artifacts</h2>
              {_open_first(manifest)}
              <div class="quick-links" data-artifact-links aria-label="Primary artifact links">
                {_source_links(manifest)}
              </div>
            </section>
            <section class="panel checksum-panel" id="checksum-review">
              <h2>Checksum Review</h2>
              <p>{escape(checksum_action)}</p>
              <div class="quick-links">
                {_artifact_link(manifest, ("manifest_json",), "manifest.json")}
                {_artifact_link(manifest, ("checksum_manifest",), "checksum_manifest.json")}
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
        </aside>
      </section>
      <section class="panel full-width-artifacts" id="raw-evidence-links">
        <h2>Raw Evidence Quick Links</h2>
        <div class="raw-evidence-groups" data-raw-evidence-links>
          {_raw_evidence_quick_links(manifest)}
        </div>
      </section>
    </main>
  </div>
  {loader_script}
</body>
</html>
"""
    return html
