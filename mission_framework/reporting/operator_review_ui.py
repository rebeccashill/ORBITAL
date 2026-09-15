from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

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
        f"{_kv('Weather source', weather_readiness.get('source'))}"
        f"{_kv('Weather timestamp', weather_readiness.get('timestamp_utc'))}"
        f"{_kv('Weather freshness', weather_readiness.get('freshness_status'))}"
        f"{_kv('Weather action', _short_text(weather_readiness.get('operator_action'), limit=130))}"
        f"{_kv('Regulatory provenance', _status_label(regulatory_provenance.get('status')), _status_class(regulatory_provenance.get('status')))}"
        f"{_kv('Authority', regulatory_provenance.get('authority'))}"
        f"{_kv('Date checked', regulatory_provenance.get('date_checked_utc'))}"
        f"{_kv('Expiration', regulatory_provenance.get('expiration_date'))}"
        f"{_kv('Operator confirmation', regulatory_provenance.get('operator_confirmation_status'))}"
        f"{_kv('Checksum evidence', _status_label(checksum_readiness.get('status')), _status_class(checksum_readiness.get('status')))}"
        "</div>"
        '<p class="compact-note">Live weather and regulatory hooks are documentation-only unless verified outside ORBITAL.</p>'
    )
    completeness_body = (
        '<div class="compact-grid">'
        f"{_kv('Artifact coverage', evidence_completeness)}"
        f"{_kv('Missing evidence', missing_count)}"
        f"{_kv('Bundle warnings', warning_count)}"
        "</div>"
    )
    trust_body = (
        '<div class="compact-grid">'
        f"{_kv('Weather evidence', weather_status, _status_class(weather_status))}"
        f"{_kv('Robustness', robustness_status, _status_class(robustness_status))}"
        f"{_kv('Weather note', _short_text(weather_summary))}"
        f"{_kv('Robustness note', _short_text(robustness_summary))}"
        "</div>"
        f'<p class="compact-note">{escape(_short_text(sample_note.get("note"), "Verify scenario inputs before operational use."))}</p>'
    )
    warnings_body = (
        '<div class="compact-grid">'
        f"{_kv('Stale artifacts', stale_count)}"
        f"{_kv('Missing artifacts', missing_artifact_count)}"
        f"{_kv('Mismatched artifacts', mismatch_count)}"
        f"{_kv('Warning total', warning_count, _status_class('clear' if warning_count == 0 else 'review_required'))}"
        "</div>"
        f'<p class="compact-note">{escape(evidence_warning_summary)}</p>'
        f'<ul class="compact-list">{_compact_list(bundle_warnings or missing_evidence, empty="No bundle warnings captured.")}</ul>'
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
    return "\n".join(sections)


def _manifest_loader_script(manifest: Mapping[str, Any]) -> str:
    snapshot = (
        json.dumps(manifest, ensure_ascii=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    script = r"""
(function () {
  const manifestUrl = "manifest.json";
  const artifactDefinitions = [
    { ids: ["operator_dashboard"], label: "operator_dashboard.md" },
    { ids: ["constraint_audit_markdown"], label: "inspection_constraint_audit.md" },
    { ids: ["what_if_plan_markdown"], label: "what_if_plan.md" },
    { ids: ["regulatory_readiness_markdown"], label: "regulatory_readiness_report.md" },
    { ids: ["bundle_summary"], label: "evidence_bundle_summary.md" },
    { ids: ["artifact_index"], label: "artifact_index.md" },
    { ids: ["manifest_json"], label: "manifest.json" },
    { ids: ["checksum_manifest"], label: "checksum_manifest.json" },
    { ids: ["flight_path_plot"], label: "flight_path.png" },
    { ids: ["autopilot_mission_csv"], label: "autopilot_mission.csv" },
    { ids: ["mission_review_kml"], label: "mission_review.kml" },
  ];
  const rawEvidenceGroups = [
    {
      title: "Raw Markdown",
      definitions: [
        { ids: ["operator_dashboard"], label: "operator_dashboard.md" },
        { ids: ["constraint_audit_markdown"], label: "inspection_constraint_audit.md" },
        { ids: ["what_if_plan_markdown"], label: "what_if_plan.md" },
        { ids: ["regulatory_readiness_markdown"], label: "regulatory_readiness_report.md" },
        { ids: ["bundle_summary"], label: "evidence_bundle_summary.md" },
        { ids: ["artifact_index"], label: "artifact_index.md" },
      ],
    },
    {
      title: "JSON Evidence",
      definitions: [
        { ids: ["plan_json"], label: "plan.json" },
        { ids: ["constraint_audit_json"], label: "inspection_constraint_audit.json" },
        { ids: ["what_if_plan_json"], label: "what_if_plan.json" },
        { ids: ["regulatory_readiness_json"], label: "regulatory_readiness_report.json" },
        { ids: ["score_breakdown"], label: "score_breakdown.json" },
        { ids: ["weather_snapshot"], label: "weather_snapshot.json" },
        { ids: ["robustness_summary"], label: "robustness_summary.json" },
      ],
    },
    {
      title: "CSV / KML",
      definitions: [
        { ids: ["autopilot_mission_csv"], label: "autopilot_mission.csv" },
        { ids: ["mission_review_kml"], label: "mission_review.kml" },
      ],
    },
    {
      title: "Plots",
      definitions: [
        { ids: ["flight_path_plot"], label: "flight_path.png" },
      ],
    },
    {
      title: "Manifest / checksum",
      definitions: [
        { ids: ["manifest_json"], label: "manifest.json" },
        { ids: ["checksum_manifest"], label: "checksum_manifest.json" },
      ],
    },
  ];

  function objectOr(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function arrayOr(value) {
    return Array.isArray(value) ? value : [];
  }

  function text(value, fallback) {
    if (value === null || value === undefined) {
      return fallback || "not provided";
    }
    const rendered = String(value).trim();
    return rendered || fallback || "not provided";
  }

  function shortText(value, fallback, limit) {
    const rendered = text(value, fallback || "not provided");
    const max = limit || 170;
    return rendered.length <= max ? rendered : rendered.slice(0, max - 1).trimEnd() + "...";
  }

  function slug(value) {
    const rendered = text(value, "section").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return rendered || "section";
  }

  function numberText(value, unit) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "n/a";
    }
    const suffix = unit ? " " + unit : "";
    if (Math.abs(number) > 0 && Math.abs(number) < 1) {
      return Number(number.toPrecision(3)) + suffix;
    }
    return number.toFixed(1) + suffix;
  }

  function pct(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(1) + " %" : "n/a";
  }

  function intValue(value, fallback) {
    const number = parseInt(value, 10);
    return Number.isFinite(number) ? number : fallback || 0;
  }

  function statusLabel(value) {
    return text(value, "unknown").replace(/[_-]/g, " ").toUpperCase();
  }

  function statusClass(value) {
    const normalized = text(value, "unknown").toLowerCase().replace(/[ -]/g, "_");
    if (["go", "pass", "clear", "ready", "ready_for_review", "configured_source", "documented", "fresh", "live", "low"].includes(normalized)) {
      return "status-good";
    }
    if (["review", "review_required", "operator_action_required", "warning", "fallback_used", "packaged", "pending_operator_confirmation", "sample", "stale", "verify_required", "not_run", "medium", "moderate"].includes(normalized)) {
      return "status-review";
    }
    if (["modify", "fail", "failed", "elevated_risk", "expired", "missing", "high"].includes(normalized)) {
      return "status-bad";
    }
    return "status-neutral";
  }

  function countedScore(block, totalLabel) {
    const source = objectOr(block);
    if (totalLabel === "artifacts") {
      return pct(source.score) + " (" + intValue(source.present_artifacts, 0) + " / " + intValue(source.total_artifacts, 0) + " artifacts)";
    }
    return pct(source.score) + " (" + intValue(source.documented_fields, 0) + " / " + intValue(source.total_fields, 0) + " fields)";
  }

  function marginSummary(top) {
    const source = objectOr(top);
    if (!Object.keys(source).length) {
      return "not available";
    }
    const margin = objectOr(source.margin);
    return text(source.label || source.id, "Constraint") + ", " + statusLabel(source.status) + ", margin " + numberText(margin.value, margin.unit || "");
  }

  function warningKindCount(warnings, kinds) {
    const wanted = new Set(kinds);
    return arrayOr(warnings).filter((warning) => wanted.has(warning.kind)).length;
  }

  function mismatchWarningCount(evidenceWarnings, bundleWarnings) {
    if (evidenceWarnings.mismatched_artifacts !== undefined) {
      return intValue(evidenceWarnings.mismatched_artifacts, 0);
    }
    return arrayOr(bundleWarnings).filter((warning) => text(warning.kind, "").toLowerCase().includes("mismatch")).length;
  }

  function dashboardVerdict(missionStatus, regulatoryState, missingCount, warningCount) {
    if (missionStatus.replace(/ /g, "_") !== "GO") {
      return {
        label: "MODIFY",
        meaning: "Modeled constraints do not support release as configured.",
        next_action: "Modify the route, assumptions, or constraints, then regenerate the evidence bundle before operator review.",
      };
    }
    if (regulatoryState.replace(/ /g, "_") === "OPERATOR_ACTION_REQUIRED" || missingCount > 0 || warningCount > 0) {
      return {
        label: "REVIEW REQUIRED",
        meaning: "Modeled feasibility is acceptable, but operator, regulatory, or evidence review items remain.",
        next_action: "Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision.",
      };
    }
    return {
      label: "GO",
      meaning: "Modeled feasibility and bundle evidence are ready for normal operator review.",
      next_action: "Proceed to normal operator review, verify checksums, and archive the evidence bundle.",
    };
  }

  function verdictDerivation(verdict, missionStatus, regulatoryState, missingCount, warningCount) {
    let explanation = "";
    if (missionStatus.replace(/ /g, "_") !== "GO") {
      explanation = "The verdict is MODIFY because the modeled mission status is not GO.";
    } else if (regulatoryState.replace(/ /g, "_") === "OPERATOR_ACTION_REQUIRED" || missingCount > 0 || warningCount > 0) {
      explanation = "The verdict is REVIEW REQUIRED because modeled feasibility is GO but regulatory readiness, missing evidence, or bundle warnings still need operator attention.";
    } else {
      explanation = "The verdict is GO because modeled mission status is GO, regulatory readiness does not require action, and no missing evidence or bundle warnings are recorded.";
    }
    return {
      label: verdict.label,
      explanation,
      inputs: [
        { signal: "Modeled mission status", value: missionStatus, effect: "MODIFY if not GO." },
        { signal: "Regulatory readiness", value: regulatoryState, effect: "REVIEW REQUIRED when OPERATOR_ACTION_REQUIRED." },
        { signal: "Missing evidence", value: missingCount + " item(s)", effect: "REVIEW REQUIRED when greater than 0." },
        { signal: "Bundle warnings", value: warningCount + " warning(s)", effect: "REVIEW REQUIRED when greater than 0." },
      ],
    };
  }

  function artifactEntry(manifest, ids) {
    const entries = arrayOr(manifest.artifacts).concat(arrayOr(manifest.generated_artifacts));
    for (const id of ids) {
      const entry = entries.find((candidate) => candidate && candidate.id === id);
      if (entry) {
        return entry;
      }
    }
    return null;
  }

  function artifactKind(label) {
    const match = String(label).match(/\.([A-Za-z0-9]+)$/);
    return match ? match[1].toUpperCase() : "FILE";
  }

  function artifactLabelNode(label, unavailable) {
    const name = document.createElement("span");
    name.textContent = unavailable ? label + " unavailable" : label;
    const tag = document.createElement("small");
    tag.textContent = unavailable ? "Missing" : artifactKind(label);
    return [name, tag];
  }

  function artifactNode(manifest, ids, label) {
    const entry = artifactEntry(manifest, ids);
    if (entry && entry.present && entry.bundle_path) {
      const link = document.createElement("a");
      link.className = "artifact-link";
      link.href = String(entry.bundle_path).replace(/\\/g, "/");
      link.setAttribute("aria-label", "Open " + label);
      link.append(...artifactLabelNode(label, false));
      return link;
    }
    const span = document.createElement("span");
    span.className = "artifact-link artifact-unavailable unavailable";
    span.append(...artifactLabelNode(label, true));
    return span;
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((node) => {
      node.textContent = value;
    });
  }

  function setStatusText(message, className) {
    document.querySelectorAll("[data-manifest-status]").forEach((node) => {
      node.textContent = message;
      node.className = "loading-status " + (className || "status-neutral");
    });
  }

  function replaceChildren(node, children) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
    children.forEach((child) => node.appendChild(child));
  }

  function statCard(label, value, detail, className) {
    const card = document.createElement("article");
    card.className = ("signal " + (className || "")).trim();
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = text(value);
    card.append(labelNode, valueNode);
    if (detail) {
      const detailNode = document.createElement("p");
      detailNode.textContent = detail;
      card.appendChild(detailNode);
    }
    return card;
  }

  function readItem(label, value, detail, className, options) {
    const card = document.createElement("article");
    card.className = ("read-item " + (className || "") + ((options && options.wide) ? " read-action" : "")).trim();
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = text(value);
    if (options && options.field) {
      valueNode.setAttribute("data-field", options.field);
    }
    card.append(labelNode, valueNode);
    if (detail) {
      const detailNode = document.createElement("p");
      detailNode.textContent = detail;
      card.appendChild(detailNode);
    }
    return card;
  }

  function kv(label, value, className) {
    const wrapper = document.createElement("div");
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = text(value);
    if (className) {
      valueNode.className = className;
    }
    wrapper.append(labelNode, valueNode);
    return wrapper;
  }

  function section(title, summary, bodyNodes, linkNodes, id) {
    const article = document.createElement("article");
    article.className = "review-section";
    article.id = id || slug(title);
    article.tabIndex = 0;
    const heading = document.createElement("h2");
    heading.id = article.id + "-heading";
    heading.textContent = title;
    article.setAttribute("aria-labelledby", heading.id);
    const copy = document.createElement("p");
    copy.textContent = summary;
    article.append(heading, copy, ...bodyNodes);
    if (linkNodes && linkNodes.length) {
      const links = document.createElement("div");
      links.className = "section-links";
      links.append(...linkNodes);
      article.appendChild(links);
    }
    return article;
  }

  function compactGrid(items) {
    const grid = document.createElement("div");
    grid.className = "compact-grid";
    items.forEach((item) => grid.appendChild(kv(item.label, item.value, item.className)));
    return grid;
  }

  function assumptionsNode(trust) {
    const assumptions = arrayOr(objectOr(trust).model_assumptions_summary).slice(0, 3);
    if (!assumptions.length) {
      const note = document.createElement("p");
      note.className = "compact-note";
      note.textContent = "No model assumptions were captured. Operator should verify scenario inputs in the constraint audit.";
      return note;
    }
    const list = document.createElement("ul");
    list.className = "assumption-list";
    assumptions.forEach((item) => {
      const source = objectOr(item);
      const li = document.createElement("li");
      const label = document.createElement("strong");
      label.textContent = text(source.label || source.id, "Model assumption");
      const assumption = document.createElement("span");
      assumption.textContent = shortText(source.assumption, "not provided", 120);
      const note = document.createElement("em");
      note.textContent = shortText(source.operator_review_note, "Operator should verify this assumption before release.", 110);
      li.append(label, assumption, note);
      list.appendChild(li);
    });
    return list;
  }

  function artifactFreshnessNode(manifest) {
    const priority = {
      scenario_yaml: 0,
      constraint_audit_markdown: 1,
      regulatory_readiness_markdown: 2,
      what_if_plan_markdown: 3,
      weather_snapshot: 4,
      autopilot_mission_csv: 5,
      mission_review_kml: 6,
    };
    const entries = arrayOr(manifest.artifacts)
      .slice()
      .sort((a, b) => (priority[text(a && a.id, "")] ?? 99) - (priority[text(b && b.id, "")] ?? 99))
      .slice(0, 5);
    if (!entries.length) {
      const note = document.createElement("p");
      note.className = "compact-note";
      note.textContent = "No artifact freshness metadata captured.";
      return note;
    }
    const list = document.createElement("div");
    list.className = "freshness-list";
    entries.forEach((entry) => {
      const source = objectOr(entry);
      const freshness = objectOr(source.freshness);
      const stale = Boolean(freshness.stale_against_scenario);
      const status = !source.present ? "MISSING" : stale ? "STALE" : "CURRENT";
      const row = document.createElement("div");
      const label = document.createElement("span");
      label.textContent = text(source.label || source.id, "Artifact");
      const statusNode = document.createElement("strong");
      statusNode.className = statusClass(status);
      statusNode.textContent = status;
      const sourceTime = document.createElement("small");
      sourceTime.textContent = "source " + text(freshness.source_modified_utc);
      const bundleTime = document.createElement("small");
      bundleTime.textContent = "bundle " + text(freshness.bundle_modified_utc);
      row.append(label, statusNode, sourceTime, bundleTime);
      list.appendChild(row);
    });
    return list;
  }

  function trustStatusSummary(summary) {
    if (summary.missionStatus.replace(/ /g, "_") !== "GO") {
      return {
        label: "Model changes needed first",
        detail: "Modeled status is " + summary.missionStatus + "; revise the mission before release review.",
        status: summary.missionStatus,
      };
    }

    const cues = [];
    const regulatoryKey = summary.regulatoryState.replace(/ /g, "_");
    const provenanceKey = summary.regulatoryProvenanceStatus.replace(/ /g, "_");
    const weatherKey = summary.weatherStatus.replace(/ /g, "_");
    const checksumKey = summary.checksumStatus.replace(/ /g, "_");
    if (regulatoryKey === "OPERATOR_ACTION_REQUIRED" || ["STALE", "PENDING_OPERATOR_CONFIRMATION", "VERIFY_REQUIRED", "EXPIRED"].includes(provenanceKey)) {
      cues.push("regulatory confirmation");
    }
    if (["STALE", "FALLBACK_USED", "SAMPLE", "UNKNOWN"].includes(weatherKey)) {
      cues.push("weather evidence check");
    }
    if (summary.missingCount > 0) {
      cues.push(summary.missingCount + " missing evidence item(s)");
    }
    if (summary.warningCount > 0) {
      cues.push(summary.warningCount + " evidence warning(s)");
    }
    if (summary.staleMissingMismatchCount > 0) {
      cues.push(summary.staleMissingMismatchCount + " stale/missing/mismatched artifact(s)");
    }
    if (["VERIFY_REQUIRED", "NOT_RUN", "UNKNOWN"].includes(checksumKey)) {
      cues.push("checksum verification");
    }

    if (cues.length) {
      return {
        label: "Operator trust review needed",
        detail: "Check " + cues.slice(0, 4).join(", ") + ".",
        status: "review_required",
      };
    }
    return {
      label: "Trust signals clear",
      detail: "No missing evidence, bundle warnings, or trust checks are flagged.",
      status: "clear",
    };
  }

  function thirtySecondReadNode(summary) {
    const wrapper = document.createElement("section");
    wrapper.className = "thirty-second-read";
    wrapper.setAttribute("data-thirty-second-read", "");
    wrapper.setAttribute("aria-label", "30-second mission read");
    const heading = document.createElement("header");
    const label = document.createElement("span");
    label.textContent = "30-Second Mission Read";
    const summaryLine = document.createElement("strong");
    summaryLine.textContent = "Verdict, limiter, trust posture, action.";
    heading.append(label, summaryLine);
    const grid = document.createElement("div");
    grid.className = "read-grid";
    grid.append(
      readItem("Verdict", summary.verdict.label, summary.verdict.meaning, statusClass(summary.verdict.label)),
      readItem("Top constraint", summary.topSummary, "Most likely to limit release.", "signal-top"),
      readItem("Trust status", summary.trustStatus.label, summary.trustStatus.detail, statusClass(summary.trustStatus.status)),
      readItem("Next operator action", summary.verdict.next_action, "Before field release, operator authority stays outside ORBITAL.", statusClass(summary.verdict.label), { field: "next-action", wide: true })
    );
    wrapper.append(heading, grid);
    return wrapper;
  }

  function openFirstNode(manifest) {
    const wrapper = document.createElement("div");
    wrapper.className = "open-first";
    wrapper.setAttribute("data-open-first", "");
    wrapper.setAttribute("aria-label", "First artifact to open");
    const label = document.createElement("span");
    label.textContent = "Open first: first artifact to open";
    const note = document.createElement("p");
    note.textContent = "Start here for the verdict, next action, and 30-second mission read. This is the primary review surface before opening supporting artifacts.";
    wrapper.append(label, artifactNode(manifest, ["operator_dashboard"], "operator_dashboard.md"), note);
    return wrapper;
  }

  function compatibilityNode(manifest) {
    const compatibility = objectOr(manifest.ui_compatibility);
    const artifactAccess = objectOr(compatibility.artifact_access);
    const requiredFields = arrayOr(compatibility.required_top_level_fields);
    const fallbackFields = objectOr(compatibility.optional_field_fallbacks);
    const expectedFormats = arrayOr(artifactAccess.expected_formats);
    const wrapper = document.createElement("div");
    wrapper.setAttribute("data-ui-compatibility", "");
    const grid = compactGrid([
      { label: "Manifest version", value: manifest.manifest_version || compatibility.manifest_version, className: statusClass("documented") },
      { label: "UI schema", value: compatibility.schema_version },
      { label: "Required UI fields", value: requiredFields.length + " expected" },
      { label: "Fallback fields", value: Object.keys(fallbackFields).length + " documented" },
    ]);
    const fallbackNote = document.createElement("p");
    fallbackNote.className = "compact-note";
    fallbackNote.textContent = text(compatibility.optional_field_fallback_policy, "Optional UI fields use explicit fallback text.");
    const accessNote = document.createElement("p");
    accessNote.className = "compact-note";
    accessNote.textContent = "Outside-UI access: " + (expectedFormats.length ? expectedFormats.join(", ") : "Markdown, JSON, CSV, KML, PNG, manifest, checksum, dashboard") + ".";
    const unavailableNote = document.createElement("p");
    unavailableNote.className = "compact-note";
    unavailableNote.textContent = text(artifactAccess.unavailable_artifact_policy, "Unavailable artifacts render as non-link unavailable labels.");
    wrapper.append(grid, fallbackNote, accessNote, unavailableNote);
    return wrapper;
  }

  function rawEvidenceGroupNode(manifest, group) {
    const wrapper = document.createElement("section");
    wrapper.className = "quick-link-group";
    const heading = document.createElement("h3");
    heading.textContent = group.title;
    const links = document.createElement("div");
    links.className = "quick-links";
    links.append(...group.definitions.map((definition) => artifactNode(manifest, definition.ids, definition.label)));
    wrapper.append(heading, links);
    return wrapper;
  }

  function renderArtifactLinks(manifest) {
    const linkNodes = artifactDefinitions.map((definition) => artifactNode(manifest, definition.ids, definition.label));
    document.querySelectorAll("[data-artifact-links]").forEach((node) => {
      replaceChildren(node, linkNodes.map((link) => link.cloneNode(true)));
    });
  }

  function renderOpenFirst(manifest) {
    document.querySelectorAll("[data-open-first]").forEach((node) => {
      node.replaceWith(openFirstNode(manifest));
    });
  }

  function renderRawEvidenceLinks(manifest) {
    const groups = rawEvidenceGroups.map((group) => rawEvidenceGroupNode(manifest, group));
    document.querySelectorAll("[data-raw-evidence-links]").forEach((node) => {
      replaceChildren(node, groups.map((group) => group.cloneNode(true)));
    });
  }

  function renderCompatibilityPanels(manifest) {
    document.querySelectorAll("[data-ui-compatibility]").forEach((node) => {
      node.replaceWith(compatibilityNode(manifest));
    });
  }

  function renderThirtySecondRead(summary) {
    document.querySelectorAll("[data-thirty-second-read]").forEach((node) => {
      node.replaceWith(thirtySecondReadNode(summary));
    });
  }

  function manifestSummary(manifest) {
    const audit = objectOr(manifest.constraint_audit);
    const readiness = objectOr(manifest.regulatory_readiness);
    const completeness = objectOr(manifest.bundle_completeness);
    const regulatoryCompleteness = objectOr(manifest.regulatory_documentation_completeness);
    const trust = objectOr(manifest.trust_defensibility);
    const weather = objectOr(trust.weather_fallback_status);
    const weatherReadiness = objectOr(manifest.weather_evidence_readiness || trust.weather_evidence_readiness || weather);
    const regulatoryProvenance = objectOr(manifest.regulatory_evidence_provenance || trust.regulatory_evidence_provenance);
    const checksumReadiness = objectOr(manifest.checksum_evidence_readiness);
    const freshness = objectOr(manifest.freshness);
    const compatibility = objectOr(manifest.ui_compatibility);
    const robustness = objectOr(trust.uncertainty_robustness_status);
    const evidenceWarnings = objectOr(trust.evidence_warning_summary);
    const missingEvidence = arrayOr(manifest.missing_evidence);
    const bundleWarnings = arrayOr(manifest.bundle_warnings);
    const missingCount = intValue(evidenceWarnings.missing_evidence, missingEvidence.length);
    const warningCount = intValue(evidenceWarnings.bundle_warnings, bundleWarnings.length);
    const staleCount = intValue(evidenceWarnings.stale_artifacts, warningKindCount(bundleWarnings, ["stale_artifact"]));
    const missingArtifactCount = intValue(evidenceWarnings.missing_artifacts, warningKindCount(bundleWarnings, ["missing_artifact"]));
    const mismatchCount = mismatchWarningCount(evidenceWarnings, bundleWarnings);
    const staleMissingMismatchCount = staleCount + missingArtifactCount + mismatchCount;
    const missionStatus = statusLabel(audit.status);
    const missionRisk = statusLabel(audit.mission_risk);
    const regulatoryState = statusLabel(readiness.readiness_state || readiness.status);
    const regulatoryProvenanceStatus = statusLabel(regulatoryProvenance.status || regulatoryProvenance.operator_confirmation_status);
    const checksumStatus = statusLabel(checksumReadiness.status);
    const verdict = dashboardVerdict(missionStatus, regulatoryState, missingCount, warningCount);
    const topSummary = marginSummary(audit.top_limiting_constraint);
    const evidenceCompleteness = countedScore(completeness, "artifacts");
    const regulatoryDocCompleteness = countedScore(regulatoryCompleteness, "fields");
    const weatherStatus = statusLabel(weatherReadiness.status || weather.status);
    const weatherSummary = text(weatherReadiness.summary || weather.summary, "No weather evidence status captured.");
    const weatherDetail = [
      "source " + text(weatherReadiness.source, "not provided"),
      "timestamp " + text(weatherReadiness.timestamp_utc, "not provided"),
      "freshness " + text(weatherReadiness.freshness_status, "not provided"),
      "action " + text(weatherReadiness.operator_action, "Confirm current weather before release"),
    ].join("; ");
    const robustnessStatus = statusLabel(robustness.status);
    const robustnessSummary = text(robustness.summary, "No robustness / uncertainty status captured.");
    const evidenceWarningSummary = text(
      evidenceWarnings.summary,
      missingArtifactCount + " missing artifact(s), " + staleCount + " stale artifact(s), " + missingCount + " missing evidence item(s), " + warningCount + " bundle warning(s)"
    );
    const trustStatus = trustStatusSummary({
      missionStatus,
      regulatoryState,
      regulatoryProvenanceStatus,
      missingCount,
      warningCount,
      staleMissingMismatchCount,
      weatherStatus,
      checksumStatus,
    });
    return {
      audit,
      readiness,
      completeness,
      regulatoryCompleteness,
      trust,
      weather,
      weatherReadiness,
      regulatoryProvenance,
      checksumReadiness,
      freshness,
      compatibility,
      robustness,
      evidenceWarnings,
      missingEvidence,
      bundleWarnings,
      missingCount,
      warningCount,
      staleCount,
      missingArtifactCount,
      mismatchCount,
      missionStatus,
      missionRisk,
      regulatoryState,
      regulatoryProvenanceStatus,
      checksumStatus,
      verdict,
      topSummary,
      evidenceCompleteness,
      regulatoryDocCompleteness,
      weatherStatus,
      weatherSummary,
      weatherDetail,
      robustnessStatus,
      robustnessSummary,
      evidenceWarningSummary,
      staleMissingMismatchCount,
      trustStatus,
    };
  }

  function renderSignals(summary) {
    const staleMissingMismatchCount = summary.staleCount + summary.missingArtifactCount + summary.mismatchCount;
    const cards = [
      statCard("Modeled mission status", summary.missionStatus, "", "decision-signal " + statusClass(summary.missionStatus)),
      statCard("Mission risk", summary.missionRisk, "", "decision-signal " + statusClass(summary.missionRisk)),
      statCard("Top limiting constraint", summary.topSummary, "", "decision-signal signal-top"),
      statCard("Regulatory readiness", summary.regulatoryState, "", "decision-signal " + statusClass(summary.regulatoryState)),
      statCard("Evidence completeness", summary.evidenceCompleteness, "Expected bundle artifacts", "status-neutral"),
      statCard("Regulatory documentation", summary.regulatoryDocCompleteness, "Documentation-only evidence fields", "status-neutral documentation-signal"),
      statCard("Weather evidence", summary.weatherStatus, shortText(summary.weatherDetail, "No weather evidence status captured.", 150), statusClass(summary.weatherStatus)),
      statCard("Robustness / uncertainty", summary.robustnessStatus, summary.robustnessSummary, statusClass(summary.robustnessStatus)),
      statCard("Missing evidence count", String(summary.missingCount), "Artifacts or documentation fields requiring operator attention", "warning-signal " + statusClass(summary.missingCount === 0 ? "clear" : "review_required")),
      statCard("Stale / missing / mismatched evidence", String(staleMissingMismatchCount), summary.staleCount + " stale, " + summary.missingArtifactCount + " missing, " + summary.mismatchCount + " mismatched", "warning-signal " + statusClass(staleMissingMismatchCount === 0 ? "clear" : "review_required")),
      statCard("Evidence warnings", String(summary.warningCount), summary.evidenceWarningSummary, "warning-signal " + statusClass(summary.evidenceWarnings.status)),
    ];
    document.querySelectorAll("[data-signals]").forEach((node) => replaceChildren(node, cards.map((card) => card.cloneNode(true))));
  }

  function renderReviewSections(manifest, summary) {
    const review = objectOr(manifest.operator_review);
    const regulatoryStatus = objectOr(manifest.regulatory_evidence_status);
    const approvalChecklist = objectOr(manifest.approval_checklist);
    const sampleNote = objectOr(summary.trust.sample_data_demo_note);
    const weatherReadiness = objectOr(summary.weatherReadiness);
    const regulatoryProvenance = objectOr(summary.regulatoryProvenance);
    const checksumReadiness = objectOr(summary.checksumReadiness);
    const missingRegulatory = arrayOr(regulatoryStatus.missing);
    const pendingCount = intValue(approvalChecklist.pending_count, intValue(approvalChecklist.item_count, 0));
    const staleMissingMismatchCount = summary.staleCount + summary.missingArtifactCount + summary.mismatchCount;

    const artifactCopy = document.createElement("p");
    artifactCopy.className = "compact-note";
    artifactCopy.textContent = "Open source artifacts directly; this page summarizes them without replacing Markdown, JSON, CSV, KML, or checksum files.";

    const trustNote = document.createElement("p");
    trustNote.className = "compact-note";
    trustNote.textContent = shortText(sampleNote.note, "Verify scenario inputs before operational use.");

    const warningsNote = document.createElement("p");
    warningsNote.className = "compact-note";
    warningsNote.textContent = summary.evidenceWarningSummary;
    const warningList = document.createElement("ul");
    warningList.className = "compact-list";
    const warningItem = document.createElement("li");
    warningItem.textContent = summary.bundleWarnings.length || summary.missingEvidence.length ? "Open manifest.json for warning details." : "No bundle warnings captured.";
    warningList.appendChild(warningItem);

    const metadataNote = document.createElement("p");
    metadataNote.className = "compact-note";
    metadataNote.textContent = "Review metadata is documentation-only and does not change release authority.";

    const sections = [
      section("Feasibility", "Modeled mission feasibility and the constraint most likely to limit release.", [
        compactGrid([
          { label: "Modeled status", value: summary.missionStatus, className: statusClass(summary.missionStatus) },
          { label: "Mission risk", value: summary.missionRisk, className: statusClass(summary.missionRisk) },
          { label: "Top constraint", value: summary.topSummary },
        ]),
      ], [artifactNode(manifest, ["constraint_audit_markdown"], "Constraint audit")], "feasibility"),
      section("Regulatory Readiness", "Documentation-only readiness signals for operator confirmation outside ORBITAL.", [
        compactGrid([
          { label: "Readiness", value: summary.regulatoryState, className: statusClass(summary.regulatoryState) },
          { label: "Documentation", value: summary.regulatoryDocCompleteness },
          { label: "Checklist pending", value: pendingCount },
          { label: "Missing fields", value: missingRegulatory.length },
        ]),
      ], [artifactNode(manifest, ["regulatory_readiness_markdown"], "Regulatory report")], "regulatory-readiness"),
      section("Weather / Live Evidence", "Source, freshness, provenance, and operator-action hooks for operational evidence review.", [
        (() => {
          const grid = compactGrid([
            { label: "Weather status", value: statusLabel(weatherReadiness.status), className: statusClass(weatherReadiness.status) },
            { label: "Weather source", value: weatherReadiness.source },
            { label: "Weather timestamp", value: weatherReadiness.timestamp_utc },
            { label: "Weather freshness", value: weatherReadiness.freshness_status },
            { label: "Weather action", value: shortText(weatherReadiness.operator_action, "Confirm current weather before release.", 130) },
            { label: "Regulatory provenance", value: statusLabel(regulatoryProvenance.status), className: statusClass(regulatoryProvenance.status) },
            { label: "Authority", value: regulatoryProvenance.authority },
            { label: "Date checked", value: regulatoryProvenance.date_checked_utc },
            { label: "Expiration", value: regulatoryProvenance.expiration_date },
            { label: "Operator confirmation", value: regulatoryProvenance.operator_confirmation_status },
            { label: "Checksum evidence", value: statusLabel(checksumReadiness.status), className: statusClass(checksumReadiness.status) },
          ]);
          grid.classList.add("evidence-readiness-grid");
          return grid;
        })(),
        (() => {
          const note = document.createElement("p");
          note.className = "compact-note";
          note.textContent = "Live weather and regulatory hooks are documentation-only unless verified outside ORBITAL.";
          return note;
        })(),
      ], [artifactNode(manifest, ["weather_snapshot"], "Weather snapshot"), artifactNode(manifest, ["regulatory_readiness_markdown"], "Regulatory report")], "live-evidence-readiness"),
      section("Evidence Completeness", "Expected bundle artifacts and missing evidence counts.", [
        compactGrid([
          { label: "Artifact coverage", value: summary.evidenceCompleteness },
          { label: "Missing evidence", value: summary.missingCount },
          { label: "Bundle warnings", value: summary.warningCount },
        ]),
      ], [artifactNode(manifest, ["manifest_json"], "Manifest"), artifactNode(manifest, ["checksum_manifest"], "Checksums")], "evidence-completeness"),
      section("Trust / Defensibility", "Weather evidence, uncertainty, and model-context signals for audit review.", [
        compactGrid([
          { label: "Weather evidence", value: summary.weatherStatus, className: statusClass(summary.weatherStatus) },
          { label: "Robustness", value: summary.robustnessStatus, className: statusClass(summary.robustnessStatus) },
          { label: "Weather note", value: shortText(summary.weatherSummary) },
          { label: "Robustness note", value: shortText(summary.robustnessSummary) },
        ]),
        trustNote,
      ], [artifactNode(manifest, ["operator_dashboard"], "Dashboard MD")], "trust-defensibility"),
      section("Warnings", "Stale, missing, mismatched, or otherwise review-required evidence signals.", [
        compactGrid([
          { label: "Stale artifacts", value: summary.staleCount },
          { label: "Missing artifacts", value: summary.missingArtifactCount },
          { label: "Mismatched artifacts", value: summary.mismatchCount },
          { label: "Warning total", value: summary.warningCount, className: statusClass(summary.warningCount === 0 ? "clear" : "review_required") },
        ]),
        warningsNote,
        warningList,
      ], [artifactNode(manifest, ["checksum_manifest"], "Checksum manifest")], "warnings"),
      section("Artifact Navigation", "Shortcuts to the underlying source-of-truth bundle files.", [
        openFirstNode(manifest),
        artifactCopy,
      ], artifactDefinitions.map((definition) => artifactNode(manifest, definition.ids, definition.label)), "artifact-navigation"),
      section("Operator Review Metadata", "Current review-state fields captured for documentation only.", [
        compactGrid([
          { label: "Status", value: text(review.status).replace(/_/g, " ") },
          { label: "Decision", value: text(review.operator_decision, "pending operator review") },
          { label: "Reviewer", value: text(review.reviewer_name) },
          { label: "Timestamp", value: text(review.review_timestamp_utc) },
        ]),
        metadataNote,
      ], [], "operator-review-metadata"),
    ];

    document.querySelectorAll("[data-review-sections]").forEach((node) => replaceChildren(node, sections.map((item) => item.cloneNode(true))));
  }

  function renderTrustPanels(manifest, summary) {
    const derivation = verdictDerivation(summary.verdict, summary.missionStatus, summary.regulatoryState, summary.missingCount, summary.warningCount);
    document.querySelectorAll("[data-why-verdict]").forEach((node) => {
      const heading = document.createElement("h2");
      heading.textContent = "Why This Verdict?";
      const explanation = document.createElement("p");
      explanation.textContent = derivation.explanation;
      const grid = compactGrid(derivation.inputs.map((item) => ({
        label: item.signal,
        value: item.value + " - " + item.effect,
        className: statusClass(item.value),
      })));
      replaceChildren(node, [heading, explanation, grid]);
    });
    document.querySelectorAll("[data-model-assumptions]").forEach((node) => {
      const heading = document.createElement("h2");
      heading.textContent = "Model Assumptions";
      replaceChildren(node, [heading, assumptionsNode(summary.trust)]);
    });
    document.querySelectorAll("[data-artifact-freshness]").forEach((node) => {
      const heading = document.createElement("h2");
      heading.textContent = "Artifact Freshness";
      replaceChildren(node, [heading, artifactFreshnessNode(manifest)]);
    });
  }

  function renderManifest(manifest, statusMessage, statusKind) {
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
      throw new Error("manifest JSON is not an object");
    }
    const summary = manifestSummary(manifest);
    const missionName = text(summary.audit.mission_id || String(manifest.scenario_path || "scenario").split(/[\\/]/).pop().replace(/\.[^.]+$/, ""), "scenario");
    setText("[data-field='mission-name']", missionName);
    const verdictNodes = document.querySelectorAll("[data-field='verdict-label']");
    verdictNodes.forEach((node) => {
      node.textContent = summary.verdict.label;
      node.className = "verdict-badge " + statusClass(summary.verdict.label);
    });
    setText("[data-field='verdict-meaning']", summary.verdict.meaning);
    setText("[data-field='next-action']", summary.verdict.next_action);
    setText("[data-field='manifest-version']", text(manifest.manifest_version || manifest.ui_manifest_version || summary.compatibility.manifest_version, "legacy / not provided"));
    setText("[data-field='generated-timestamp']", text(summary.freshness.generated_timestamp_utc));
    setText("[data-field='checksum-status']", statusLabel(summary.checksumReadiness.status));
    renderThirtySecondRead(summary);
    renderSignals(summary);
    renderArtifactLinks(manifest);
    renderOpenFirst(manifest);
    renderRawEvidenceLinks(manifest);
    renderCompatibilityPanels(manifest);
    renderReviewSections(manifest, summary);
    renderTrustPanels(manifest, summary);
    setStatusText(statusMessage, statusKind);
  }

  function fallbackManifest() {
    const source = document.getElementById("manifest-snapshot");
    if (!source) {
      throw new Error("embedded manifest snapshot is missing");
    }
    return JSON.parse(source.textContent);
  }

  async function loadManifest() {
    try {
      const response = await fetch(manifestUrl, { cache: "no-store" });
      if (!response.ok) {
        throw new Error("manifest.json returned HTTP " + response.status);
      }
      const manifest = await response.json();
      renderManifest(manifest, "Loaded primary data from manifest.json. No backend database is required.", "status-good");
    } catch (error) {
      try {
        renderManifest(fallbackManifest(), "Using embedded fallback snapshot because manifest.json could not be loaded or parsed: " + error.message, "status-review");
      } catch (fallbackError) {
        setStatusText("Manifest JSON could not be loaded or parsed, and the embedded fallback snapshot is unavailable. Static fallback text remains visible.", "status-bad");
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadManifest);
  } else {
    loadManifest();
  }
})();
"""
    return (
        f'<script type="application/json" id="manifest-snapshot">{snapshot}</script>\n'
        f"<script>{script}</script>"
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
    regulatory_provenance = (
        manifest.get("regulatory_evidence_provenance")
        or trust.get("regulatory_evidence_provenance")
        or {}
    )

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
    stale_missing_mismatch_count = stale_count + missing_artifact_count + mismatch_count
    regulatory_provenance_status = _status_label(
        regulatory_provenance.get("status")
        or regulatory_provenance.get("operator_confirmation_status")
    )
    checksum_status = _status_label(checksum_readiness.get("status"))
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
    weather_detail = "; ".join(
        [
            f"source {_text(weather_readiness.get('source'))}",
            f"timestamp {_text(weather_readiness.get('timestamp_utc'))}",
            f"freshness {_text(weather_readiness.get('freshness_status'))}",
            "action "
            f"{_text(weather_readiness.get('operator_action'), 'Confirm current weather before release.')}",
        ]
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
    trust_status = _trust_status_summary(
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        regulatory_provenance_status=regulatory_provenance_status,
        missing_count=missing_count,
        warning_count=warning_count,
        stale_missing_mismatch_count=stale_missing_mismatch_count,
        weather_status=weather_status,
        checksum_status=checksum_status,
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
    loader_script = _manifest_loader_script(manifest)

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
            _stat_card(
                "Evidence completeness",
                evidence_completeness,
                "Expected bundle artifacts",
                "status-neutral",
            ),
            _stat_card(
                "Regulatory documentation",
                regulatory_doc_completeness,
                "Documentation-only evidence fields",
                "status-neutral documentation-signal",
            ),
            _stat_card(
                "Weather evidence",
                weather_status,
                _short_text(weather_detail, limit=150),
                _status_class(weather_status),
            ),
            _stat_card(
                "Robustness / uncertainty",
                robustness_status,
                robustness_summary,
                _status_class(robustness_status),
            ),
            _stat_card(
                "Missing evidence count",
                f"{missing_count}",
                "Artifacts or documentation fields requiring operator attention",
                f"warning-signal {_status_class('clear' if missing_count == 0 else 'review_required')}",
            ),
            _stat_card(
                "Stale / missing / mismatched evidence",
                f"{stale_missing_mismatch_count}",
                f"{stale_count} stale, {missing_artifact_count} missing, {mismatch_count} mismatched",
                f"warning-signal {_status_class('clear' if stale_missing_mismatch_count == 0 else 'review_required')}",
            ),
            _stat_card(
                "Evidence warnings",
                f"{warning_count}",
                evidence_warning_summary,
                f"warning-signal {_status_class(evidence_warnings.get('status'))}",
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
    * {{ box-sizing: border-box; }}
    html {{ max-width: 100%; overflow-x: hidden; }}
    body {{
      margin: 0;
      max-width: 100%;
      overflow-x: hidden;
      color: #17212b;
      background: #f2f4f7;
      font-family: "Segoe UI", Arial, Helvetica, sans-serif;
      font-size: 16px;
      line-height: 1.45;
    }}
    a {{ color: #0b5d95; font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    a:focus-visible,
    button:focus-visible,
    .review-section:focus-visible {{
      outline: 3px solid #0f5f9f;
      outline-offset: 3px;
    }}
    .skip-link {{
      position: absolute;
      top: -48px;
      left: 16px;
      z-index: 20;
      border-radius: 6px;
      background: #ffffff;
      border: 2px solid #0f5f9f;
      color: #0f5f9f;
      padding: 8px 10px;
      box-shadow: 0 6px 16px rgba(22, 34, 45, 0.16);
    }}
    .skip-link:focus {{
      top: 12px;
    }}
    .shell {{ min-height: 100vh; }}
    .topbar {{
      background: #ffffff;
      border-bottom: 1px solid #d8dee7;
      border-top: 4px solid #0f5f9f;
      padding: 0 24px;
    }}
    .topbar-inner {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 13px 0;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
    }}
    .topbar strong {{ display: block; font-size: 20px; }}
    .topbar span {{ color: #607080; }}
    .topbar-actions {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      align-items: center;
    }}
    .read-only-pill {{
      border: 1px solid #aab7c4;
      border-radius: 8px;
      color: #34495e;
      font-size: 12px;
      font-weight: 800;
      padding: 6px 9px;
      text-transform: uppercase;
      white-space: nowrap;
      background: #f8fafc;
    }}
    .print-button {{
      border: 1px solid #0f5f9f;
      border-radius: 8px;
      background: #0f5f9f;
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 800;
      min-height: 34px;
      padding: 6px 10px;
    }}
    .print-button:hover {{ background: #0a4d82; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    .dashboard-grid {{
      display: grid;
      grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
      gap: 16px;
      align-items: start;
    }}
    .dashboard-primary {{
      display: grid;
      gap: 12px;
      min-width: 0;
    }}
    .review-lead {{
      display: grid;
      gap: 12px;
    }}
    .priority-stack {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      min-width: 0;
    }}
    .priority-stack .why-verdict {{ grid-column: 1 / -1; }}
    .supporting-evidence {{
      display: grid;
      gap: 16px;
      margin-top: 16px;
    }}
    .supporting-main {{
      display: grid;
      gap: 12px;
      min-width: 0;
    }}
    .verdict-band, .thirty-second-read, .panel, .signal, .route-preview, .review-section {{
      background: #ffffff;
      border: 1px solid #d8dee7;
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(22, 34, 45, 0.06);
    }}
    .verdict-band {{
      padding: 18px;
      border-left: 5px solid #0f5f9f;
      box-shadow: 0 8px 24px rgba(20, 47, 72, 0.08);
    }}
    .eyebrow {{
      color: #607080;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 8px 0 8px;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    h2 {{ margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }}
    .verdict-badge {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      max-width: 100%;
      min-height: 31px;
      border-radius: 8px;
      padding: 4px 10px;
      font-weight: 800;
      border: 1px solid currentColor;
      font-size: 18px;
      vertical-align: middle;
      overflow-wrap: anywhere;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45);
    }}
    .verdict-badge::before {{
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      flex: 0 0 auto;
    }}
    .status-good {{ color: #0f5f3d; background: #edf8f2; border-color: #8cc8a8; }}
    .status-review {{ color: #704200; background: #fff5db; border-color: #d6a13b; }}
    .status-bad {{ color: #941919; background: #fff0f0; border-color: #dc8d8d; }}
    .status-neutral {{ color: #3f5061; background: #f4f7fa; border-color: #cbd6df; }}
    .boundary-callout {{
      margin: 12px 0 0;
      padding: 10px 11px;
      color: #263847;
      background: #f8fafb;
      border: 1px solid #d8dee7;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 700;
    }}
    .next-action {{
      margin: 0;
      padding: 14px 14px 14px 16px;
      border-left: 4px solid #0f5f9f;
      background: #eef6fb;
      border-radius: 8px;
      border-top: 1px solid #c8dff1;
      border-right: 1px solid #c8dff1;
      border-bottom: 1px solid #c8dff1;
      box-shadow: 0 1px 2px rgba(15, 95, 159, 0.06);
    }}
    .next-action strong {{ display: block; font-size: 15px; }}
    .next-action p {{ margin: 6px 0 0; }}
    .thirty-second-read {{
      display: grid;
      gap: 10px;
      padding: 14px;
      border-left: 5px solid #155e63;
      box-shadow: 0 6px 18px rgba(21, 94, 99, 0.08);
    }}
    .thirty-second-read header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px 12px;
      align-items: baseline;
    }}
    .thirty-second-read header span {{
      color: #155e63;
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }}
    .thirty-second-read header strong {{
      color: #425466;
      font-size: 13px;
    }}
    .read-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .read-item {{
      min-height: 92px;
      border: 1px solid #d8dee7;
      border-left: 4px solid #9dadbb;
      border-radius: 8px;
      background: #f9fbfc;
      padding: 10px;
      overflow-wrap: anywhere;
    }}
    .read-item.read-action {{ grid-column: span 3; }}
    .read-item.signal-top {{ border-left-color: #0f5f9f; background: #f5fbff; }}
    .read-item.status-good {{ border-left-color: #2d8f5d; }}
    .read-item.status-review {{ border-left-color: #c97f12; }}
    .read-item.status-bad {{ border-left-color: #c94040; }}
    .read-item span {{
      display: block;
      color: #607080;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }}
    .read-item strong {{
      display: block;
      margin-top: 5px;
      color: #17212b;
      font-size: 15px;
      line-height: 1.22;
    }}
    .read-item p {{
      margin: 6px 0 0;
      color: #425466;
      font-size: 12px;
    }}
    .freshness-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .freshness-strip article {{
      min-height: 86px;
      border: 1px solid #d8dee7;
      border-left: 4px solid #7d8b99;
      border-radius: 8px;
      background: #ffffff;
      padding: 11px;
      box-shadow: 0 1px 2px rgba(22, 34, 45, 0.06);
      overflow-wrap: anywhere;
    }}
    .freshness-strip span {{
      display: block;
      color: #607080;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .freshness-strip strong {{
      display: block;
      margin-top: 5px;
      font-size: 15px;
      line-height: 1.2;
    }}
    .freshness-strip small {{
      display: block;
      margin-top: 5px;
      color: #425466;
      font-size: 12px;
    }}
    .review-order {{
      background: #ffffff;
      border: 1px solid #d8dee7;
      border-left: 5px solid #263847;
      border-radius: 8px;
      padding: 13px;
      box-shadow: 0 1px 2px rgba(22, 34, 45, 0.06);
    }}
    .review-order > span {{
      display: block;
      color: #607080;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .review-order p {{
      margin: 4px 0 10px;
      color: #263847;
      font-weight: 800;
    }}
    .review-order ol {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
      gap: 8px;
    }}
    .review-order a {{
      display: grid;
      gap: 3px;
      height: 100%;
      min-height: 92px;
      border: 1px solid #d8dee7;
      border-radius: 8px;
      background: #f9fbfc;
      color: #17212b;
      padding: 9px;
    }}
    .review-order a:hover {{
      background: #eef6fb;
      border-color: #8fb8d4;
      text-decoration: none;
    }}
    .review-order a span {{
      width: 24px;
      height: 24px;
      border-radius: 50%;
      display: inline-grid;
      place-items: center;
      color: #ffffff;
      background: #0f5f9f;
      font-size: 12px;
      font-weight: 800;
    }}
    .review-order a strong {{
      display: block;
      font-size: 14px;
      line-height: 1.2;
    }}
    .review-order a small {{
      color: #526578;
      font-size: 12px;
      line-height: 1.25;
    }}
    .why-verdict {{
      padding: 14px;
      border-left: 4px solid #7255a1;
      background: #fbf9ff;
    }}
    .why-verdict h2 {{ margin-bottom: 6px; }}
    .why-verdict p {{ margin: 0 0 10px; color: #425466; }}
    .signals {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
      gap: 10px;
    }}
    .signal {{
      padding: 12px;
      min-height: 98px;
      overflow-wrap: anywhere;
      border-left: 4px solid #c9d4df;
    }}
    .signal.decision-signal {{
      min-height: 116px;
      border-top-color: #cad6df;
      box-shadow: 0 5px 16px rgba(22, 34, 45, 0.07);
    }}
    .signal.signal-top {{ border-left-color: #0f5f9f; background: #f9fcfe; }}
    .signal.status-good {{ border-left-color: #2d8f5d; }}
    .signal.status-review {{ border-left-color: #c97f12; }}
    .signal.status-bad {{ border-left-color: #c94040; }}
    .signal.status-neutral {{ border-left-color: #9dadbb; }}
    .signal span {{ display: block; color: #607080; font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .signal strong {{
      display: block;
      margin-top: 6px;
      font-size: 16px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .signal p {{
      margin: 6px 0 0;
      color: #425466;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .warning-signal.status-review {{ border-left-color: #c97f12; background: #fff8e8; }}
    .warning-signal.status-bad {{ border-left-color: #c94040; background: #fff0f0; }}
    .warning-signal.status-good {{ border-left-color: #2d8f5d; background: #f3faf6; }}
    .documentation-signal {{ border-left-color: #8b9aaa !important; background: #f8fafb; }}
    .side-stack {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      align-items: start;
    }}
    .panel {{ padding: 15px; }}
    .boundary-list {{ margin: 0; padding-left: 18px; }}
    .side-stack .product-boundary-panel {{
      grid-column: span 2;
    }}
    .side-stack .product-boundary-panel .boundary-list {{
      columns: 2;
      column-gap: 20px;
    }}
    .boundary-list li {{ margin: 8px 0; }}
    .route-preview {{ margin: 0; padding: 14px; }}
    .route-preview img {{ display: block; width: 100%; height: auto; border-radius: 6px; border: 1px solid #d8dee7; }}
    .route-preview figcaption {{ margin-top: 8px; color: #607080; font-size: 13px; }}
    .route-missing {{ color: #607080; }}
    .quick-links {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .raw-evidence-groups {{
      display: grid;
      gap: 11px;
    }}
    .quick-link-group {{
      display: grid;
      gap: 7px;
    }}
    .quick-link-group h3 {{
      margin: 0;
      color: #425466;
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .artifact-link {{
      border: 1px solid #c9d4df;
      border-radius: 8px;
      padding: 8px 9px;
      background: #fbfcfd;
      font-size: 13px;
      line-height: 1.2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 38px;
      transition: border-color 120ms ease, background 120ms ease, box-shadow 120ms ease;
    }}
    a.artifact-link:hover {{
      background: #eef6fb;
      border-color: #8fb8d4;
      box-shadow: 0 2px 8px rgba(15, 95, 159, 0.12);
      text-decoration: none;
    }}
    .artifact-link span {{ min-width: 0; overflow-wrap: anywhere; }}
    .artifact-link small {{
      color: #526578;
      background: #eef2f6;
      border: 1px solid #d6dee7;
      border-radius: 999px;
      flex: 0 0 auto;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      text-transform: uppercase;
    }}
    .artifact-unavailable {{
      background: #f5f6f8;
      border-style: dashed;
      color: #6c7885;
    }}
    .open-first {{
      border: 1px solid #0f5f9f;
      border-left: 5px solid #0f5f9f;
      border-radius: 8px;
      background: #eef6fc;
      padding: 13px;
      margin-bottom: 12px;
      box-shadow: 0 3px 12px rgba(15, 95, 159, 0.1);
    }}
    .open-first > span {{
      display: block;
      color: #425466;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .open-first a {{
      display: flex;
      margin-top: 4px;
      font-size: 17px;
      background: #ffffff;
    }}
    .open-first p {{
      margin: 6px 0 0;
      color: #425466;
      font-size: 13px;
    }}
    .loading-status {{
      border: 1px solid #c9d4df;
      border-radius: 8px;
      margin: 12px 0 0;
      padding: 10px;
      font-size: 13px;
      font-weight: 700;
    }}
    .loading-status.status-good {{ background: #edf8f2; border-color: #8fc8a8; color: #135c3a; }}
    .loading-status.status-review {{ background: #fff5dc; border-color: #d8ad49; color: #744400; }}
    .loading-status.status-bad {{ background: #fff0f0; border-color: #db8f8f; color: #941919; }}
    .unavailable {{ color: #6f7d8a; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .meta-grid div {{ padding: 10px; background: #f9fbfc; border-radius: 6px; border: 1px solid #e3e8ee; }}
    .meta-grid span {{ display: block; color: #607080; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .meta-grid strong {{
      display: block;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}
    .review-sections {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .dashboard-review-sections {{ margin-top: 0; }}
    .dashboard-review-sections {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .review-section {{
      padding: 14px;
      min-height: 196px;
      overflow-wrap: anywhere;
      scroll-margin-top: 18px;
    }}
    .review-section h2 {{ font-size: 17px; margin-bottom: 8px; }}
    .review-section p {{ margin: 0 0 12px; color: #425466; font-size: 14px; }}
    .compact-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .compact-grid div {{
      border: 1px solid #e3e8ee;
      border-radius: 6px;
      background: #f9fbfc;
      padding: 8px;
      min-height: 60px;
    }}
    .compact-grid span {{
      display: block;
      color: #607080;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .compact-grid strong {{
      display: block;
      margin-top: 4px;
      font-size: 14px;
      line-height: 1.25;
    }}
    .compact-grid strong.status-good,
    .compact-grid strong.status-review,
    .compact-grid strong.status-bad,
    .compact-grid strong.status-neutral {{
      border-radius: 6px;
      padding: 3px 6px;
      width: fit-content;
    }}
    .compact-note {{ margin-top: 10px !important; }}
    .compact-list {{
      margin: 8px 0 0;
      padding-left: 18px;
      color: #425466;
      font-size: 13px;
    }}
    .assumption-list {{
      display: grid;
      gap: 8px;
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    .assumption-list li {{
      border: 1px solid #e3e8ee;
      border-radius: 6px;
      background: #f9fbfc;
      padding: 9px;
    }}
    .assumption-list strong,
    .assumption-list span,
    .assumption-list em {{
      display: block;
      overflow-wrap: anywhere;
    }}
    .assumption-list strong {{ font-size: 14px; }}
    .assumption-list span {{ margin-top: 4px; color: #425466; font-size: 13px; }}
    .assumption-list em {{ margin-top: 5px; color: #5d4d1e; font-size: 12px; font-style: normal; font-weight: 700; }}
    .freshness-list {{
      display: grid;
      gap: 8px;
    }}
    .freshness-list div {{
      border: 1px solid #e3e8ee;
      border-radius: 6px;
      background: #f9fbfc;
      padding: 9px;
    }}
    .freshness-list span,
    .freshness-list strong,
    .freshness-list small {{
      display: block;
      overflow-wrap: anywhere;
    }}
    .freshness-list span {{ color: #607080; font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .freshness-list strong {{ margin-top: 4px; border-radius: 6px; padding: 3px 6px; width: fit-content; }}
    .freshness-list small {{ margin-top: 4px; color: #425466; font-size: 12px; }}
    .section-links {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .side-stack #source-artifacts,
    .side-stack #raw-evidence-links {{
      grid-column: span 2;
    }}
    .side-stack .quick-links {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .side-stack .raw-evidence-groups {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .side-stack .raw-evidence-groups .quick-links {{ grid-template-columns: 1fr; }}
    .evidence-readiness-grid div:nth-child(2),
    .evidence-readiness-grid div:nth-child(5) {{ grid-column: span 2; }}
    #trust-defensibility .compact-grid div:nth-child(n+3) {{ grid-column: span 2; }}
    #artifact-navigation .section-links {{ grid-template-columns: 1fr; }}
    .section-links .artifact-link {{ font-size: 13px; }}
    @media (max-width: 1100px) {{
      .side-stack {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .side-stack #source-artifacts,
      .side-stack #raw-evidence-links {{
        grid-column: span 2;
      }}
    }}
    @media (max-width: 920px) {{
      .dashboard-grid {{
        grid-template-columns: 1fr;
      }}
      .side-stack {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .side-stack .product-boundary-panel,
      .side-stack #source-artifacts,
      .side-stack #raw-evidence-links {{
        grid-column: span 2;
      }}
      .review-order ol {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .signals {{ grid-template-columns: repeat(3, minmax(150px, 1fr)); }}
      .review-sections {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 620px) {{
      main {{ padding: 12px; }}
      .topbar {{ padding: 0 16px; }}
      .topbar-inner {{ padding: 10px 0; align-items: flex-start; flex-direction: column; gap: 8px; }}
      .topbar strong {{ font-size: 18px; }}
      .topbar-inner > div:first-child span {{ font-size: 13px; }}
      .topbar-actions {{ gap: 6px; }}
      .print-button {{ display: none; }}
      main,
      .dashboard-grid,
      .review-lead,
      .priority-stack,
      .dashboard-context,
      .supporting-evidence,
      .supporting-main,
      .side-stack,
      .verdict-band,
      .thirty-second-read,
      .next-action,
      .panel,
      .route-preview,
      .signal,
      .review-section {{
        min-width: 0;
        max-width: 100%;
      }}
      .review-lead {{ gap: 8px; }}
      h1 {{ display: block; font-size: 23px; margin: 6px 0; }}
      .verdict-band {{ padding: 14px; }}
      .verdict-band [data-field="verdict-meaning"] {{
        margin: 8px 0 0;
        font-size: 14px;
        line-height: 1.3;
      }}
      .boundary-callout {{ display: none; }}
      .verdict-badge {{ display: flex; margin-top: 8px; width: fit-content; font-size: 16px; }}
      .thirty-second-read {{ padding: 10px; gap: 7px; }}
      .thirty-second-read header {{ gap: 3px; }}
      .read-grid {{ gap: 6px; }}
      .read-item {{ min-height: 0; padding: 8px; }}
      .read-item strong {{ font-size: 14px; }}
      .read-item p {{ margin-top: 4px; font-size: 11px; line-height: 1.2; }}
      .signals, .priority-stack, .meta-grid, .compact-grid, .review-sections, .quick-links, .section-links, .review-order ol, .freshness-strip, .read-grid, .side-stack, .raw-evidence-groups {{ grid-template-columns: 1fr; }}
      .read-item.read-action {{ grid-column: auto; }}
      .priority-stack .why-verdict {{ grid-column: auto; }}
      .side-stack #source-artifacts,
      .side-stack .product-boundary-panel,
      .side-stack #raw-evidence-links {{
        grid-column: auto;
      }}
      .side-stack .product-boundary-panel .boundary-list {{ columns: 1; }}
      .evidence-readiness-grid div:nth-child(2),
      .evidence-readiness-grid div:nth-child(5) {{ grid-column: auto; }}
      #trust-defensibility .compact-grid div:nth-child(n+3) {{ grid-column: auto; }}
    }}
    @media print {{
      @page {{
        size: letter;
        margin: 0.45in;
      }}
      body {{
        background: #ffffff;
        color: #111827;
        font-size: 10.5px;
        line-height: 1.25;
      }}
      .shell {{
        min-height: auto;
      }}
      .skip-link,
      .print-button,
      .loading-status,
      script {{
        display: none !important;
      }}
      .topbar {{
        position: static;
        border-top: 0;
        border-bottom: 1px solid #d8dee7;
        padding: 0 0 8px;
        margin-bottom: 10px;
      }}
      .topbar-inner {{
        display: block;
        max-width: none;
        padding: 0;
      }}
      .topbar span {{
        margin-top: 2px;
      }}
      main {{
        max-width: none;
        padding: 0;
      }}
      .dashboard-grid {{
        display: flex;
        flex-direction: column;
        gap: 10px;
      }}
      .dashboard-primary {{
        display: contents;
      }}
      .review-lead {{ order: 1; }}
      .signals {{ order: 2; }}
      .dashboard-context {{ order: 3; }}
      .dashboard-review-sections {{ order: 4; }}
      .supporting-evidence {{
        display: grid;
        gap: 8px;
        margin-top: 10px;
      }}
      .review-lead,
      .priority-stack,
      .supporting-main {{
        display: grid;
        gap: 8px;
      }}
      .priority-stack {{
        grid-template-columns: 1fr 1fr;
      }}
      .priority-stack .why-verdict {{
        grid-column: span 2;
      }}
      .side-stack {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-top: 8px;
      }}
      .side-stack #source-artifacts,
      .side-stack #raw-evidence-links {{
        grid-column: span 2;
      }}
      .review-sections {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .signals {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
      }}
      .compact-grid,
      .meta-grid,
      .freshness-strip,
      .read-grid,
      .review-order ol {{
        grid-template-columns: 1fr 1fr;
        gap: 6px;
      }}
      .read-item.read-action {{
        grid-column: span 2;
      }}
      .verdict-band,
      .thirty-second-read,
      .panel,
      .signal,
      .route-preview,
      .review-section,
      .next-action,
      .review-order {{
        break-inside: avoid;
        box-shadow: none;
      }}
      .verdict-band,
      .thirty-second-read,
      .panel,
      .signal,
      .route-preview,
      .review-section,
      .review-order {{
        padding: 9px;
      }}
      .review-section {{
        min-height: 0;
      }}
      .artifact-link {{
        min-height: 0;
        padding: 5px 6px;
        font-size: 9.5px;
      }}
      #source-artifacts,
      #raw-evidence-links {{
        break-inside: auto;
      }}
      h1 {{
        font-size: 20px;
      }}
      h2 {{
        font-size: 14px;
        margin-bottom: 5px;
      }}
      .review-section p,
      .compact-note,
      .signal p,
      .read-item p,
      .freshness-strip small {{
        font-size: 10px;
      }}
      .route-preview img {{
        max-height: 210px;
        object-fit: contain;
      }}
      a[href]::after {{
        content: none;
      }}
    }}
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
        <div class="dashboard-primary">
          <div class="review-lead">
            <section class="verdict-band" id="mission-verdict" aria-label="Mission verdict">
              <span class="eyebrow" data-field="mission-name">{escape(_text(mission_name))}</span>
              <h1>Mission Verdict: <span class="verdict-badge {_status_class(verdict["label"])}" data-field="verdict-label">{escape(verdict["label"])}</span></h1>
              <p data-field="verdict-meaning">{escape(verdict["meaning"])}</p>
              <p class="boundary-callout">Decision support only; the generated evidence bundle remains the source of truth.</p>
            </section>
            {_thirty_second_read(verdict=verdict, top_summary=top_summary, trust_status=trust_status)}
          </div>
          <div class="signals" aria-label="Mission signals" data-signals>
            {cards}
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
        </div>
        <section class="review-sections dashboard-review-sections" id="review-sections" aria-label="Compact review sections" data-review-sections>
          {review_sections}
        </section>
      </section>
      <section class="supporting-evidence" aria-label="Supporting evidence and artifacts">
        <aside class="side-stack" aria-label="Product boundary and bundle artifacts">
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
          <section class="panel" data-artifact-freshness>
            <h2>Artifact Freshness</h2>
            {_artifact_freshness_preview(manifest)}
          </section>
          {_route_preview(manifest)}
          <section class="panel" id="source-artifacts">
            <h2>Source Artifacts</h2>
            {_open_first(manifest)}
            <div class="quick-links" data-artifact-links aria-label="Primary artifact links">
              {_source_links(manifest)}
            </div>
          </section>
          <section class="panel" id="raw-evidence-links">
            <h2>Raw Evidence Quick Links</h2>
            <div class="raw-evidence-groups" data-raw-evidence-links>
              {_raw_evidence_quick_links(manifest)}
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
            <h2>Data Loading</h2>
            <div class="meta-grid">
              <div><span>Primary source</span><strong>outputs/bvlos_powerline_inspection/operator_evidence_bundle/manifest.json</strong></div>
              <div><span>Runtime target</span><strong>manifest.json</strong></div>
              <div><span>Writes</span><strong>read-only UI; no bundle mutation</strong></div>
              <div><span>Storage</span><strong>no backend database required</strong></div>
            </div>
            <p class="loading-status status-neutral" data-manifest-status>Loading primary data from manifest.json...</p>
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
  {loader_script}
</body>
</html>
"""
    return html
