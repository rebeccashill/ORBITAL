from __future__ import annotations

import json
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
        "low",
    }:
        return "status-good"
    if normalized in {
        "review",
        "review_required",
        "operator_action_required",
        "warning",
        "fallback_used",
        "not_run",
        "medium",
        "moderate",
    }:
        return "status-review"
    if normalized in {"modify", "fail", "failed", "elevated_risk", "high"}:
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


def _artifact_link(manifest: Mapping[str, Any], ids: Sequence[str], label: str) -> str:
    entry = _artifact_entry(manifest, ids)
    if entry and entry.get("present") and entry.get("bundle_path"):
        return f'<a href="{_href(entry.get("bundle_path"))}">{escape(label)}</a>'
    return f'<span class="unavailable">{escape(label)} unavailable</span>'


def _open_first(manifest: Mapping[str, Any]) -> str:
    return (
        '<div class="open-first" data-open-first>'
        "<span>Open first</span>"
        f"{_artifact_link(manifest, ('operator_dashboard',), 'operator_dashboard.md')}"
        "<p>Start here for the verdict, next action, and 30-second mission read.</p>"
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


def _source_links(manifest: Mapping[str, Any]) -> str:
    links = [
        _artifact_link(manifest, ("operator_dashboard",), "operator_dashboard.md"),
        _artifact_link(
            manifest,
            ("constraint_audit_markdown",),
            "inspection_constraint_audit.md",
        ),
        _artifact_link(manifest, ("what_if_plan_markdown",), "what_if_plan.md"),
        _artifact_link(
            manifest,
            ("regulatory_readiness_markdown",),
            "regulatory_readiness_report.md",
        ),
        _artifact_link(manifest, ("bundle_summary",), "evidence_bundle_summary.md"),
        _artifact_link(manifest, ("artifact_index",), "artifact_index.md"),
        _artifact_link(manifest, ("manifest_json",), "manifest.json"),
        _artifact_link(manifest, ("checksum_manifest",), "checksum_manifest.json"),
        _artifact_link(manifest, ("flight_path_plot",), "flight_path.png"),
        _artifact_link(manifest, ("autopilot_mission_csv",), "autopilot_mission.csv"),
        _artifact_link(manifest, ("mission_review_kml",), "mission_review.kml"),
    ]
    return "\n".join(links)


def _review_section(
    title: str,
    summary: str,
    body_html: str,
    links_html: str = "",
    section_id: str = "",
) -> str:
    links = f'<div class="section-links">{links_html}</div>' if links_html else ""
    id_attr = f' id="{escape(section_id, quote=True)}"' if section_id else ""
    return (
        f'<article class="review-section"{id_attr}>'
        f"<h2>{escape(title)}</h2>"
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
    completeness_body = (
        '<div class="compact-grid">'
        f"{_kv('Artifact coverage', evidence_completeness)}"
        f"{_kv('Missing evidence', missing_count)}"
        f"{_kv('Bundle warnings', warning_count)}"
        "</div>"
    )
    trust_body = (
        '<div class="compact-grid">'
        f"{_kv('Weather fallback', weather_status, _status_class(weather_status))}"
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
            "Weather fallback, uncertainty, and model-context signals for audit review.",
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
    if (["go", "pass", "clear", "ready", "ready_for_review", "configured_source", "low"].includes(normalized)) {
      return "status-good";
    }
    if (["review", "review_required", "operator_action_required", "warning", "fallback_used", "not_run", "medium", "moderate"].includes(normalized)) {
      return "status-review";
    }
    if (["modify", "fail", "failed", "elevated_risk", "high"].includes(normalized)) {
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

  function artifactNode(manifest, ids, label) {
    const entry = artifactEntry(manifest, ids);
    if (entry && entry.present && entry.bundle_path) {
      const link = document.createElement("a");
      link.href = String(entry.bundle_path).replace(/\\/g, "/");
      link.textContent = label;
      return link;
    }
    const span = document.createElement("span");
    span.className = "unavailable";
    span.textContent = label + " unavailable";
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
    if (id) {
      article.id = id;
    }
    const heading = document.createElement("h2");
    heading.textContent = title;
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

  function openFirstNode(manifest) {
    const wrapper = document.createElement("div");
    wrapper.className = "open-first";
    wrapper.setAttribute("data-open-first", "");
    const label = document.createElement("span");
    label.textContent = "Open first";
    const note = document.createElement("p");
    note.textContent = "Start here for the verdict, next action, and 30-second mission read.";
    wrapper.append(label, artifactNode(manifest, ["operator_dashboard"], "operator_dashboard.md"), note);
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

  function manifestSummary(manifest) {
    const audit = objectOr(manifest.constraint_audit);
    const readiness = objectOr(manifest.regulatory_readiness);
    const completeness = objectOr(manifest.bundle_completeness);
    const regulatoryCompleteness = objectOr(manifest.regulatory_documentation_completeness);
    const trust = objectOr(manifest.trust_defensibility);
    const weather = objectOr(trust.weather_fallback_status);
    const robustness = objectOr(trust.uncertainty_robustness_status);
    const evidenceWarnings = objectOr(trust.evidence_warning_summary);
    const missingEvidence = arrayOr(manifest.missing_evidence);
    const bundleWarnings = arrayOr(manifest.bundle_warnings);
    const missingCount = intValue(evidenceWarnings.missing_evidence, missingEvidence.length);
    const warningCount = intValue(evidenceWarnings.bundle_warnings, bundleWarnings.length);
    const staleCount = intValue(evidenceWarnings.stale_artifacts, warningKindCount(bundleWarnings, ["stale_artifact"]));
    const missingArtifactCount = intValue(evidenceWarnings.missing_artifacts, warningKindCount(bundleWarnings, ["missing_artifact"]));
    const mismatchCount = mismatchWarningCount(evidenceWarnings, bundleWarnings);
    const missionStatus = statusLabel(audit.status);
    const missionRisk = statusLabel(audit.mission_risk);
    const regulatoryState = statusLabel(readiness.readiness_state || readiness.status);
    const verdict = dashboardVerdict(missionStatus, regulatoryState, missingCount, warningCount);
    const topSummary = marginSummary(audit.top_limiting_constraint);
    const evidenceCompleteness = countedScore(completeness, "artifacts");
    const regulatoryDocCompleteness = countedScore(regulatoryCompleteness, "fields");
    const weatherStatus = statusLabel(weather.status);
    const weatherSummary = text(weather.summary, "No weather fallback status captured.");
    const robustnessStatus = statusLabel(robustness.status);
    const robustnessSummary = text(robustness.summary, "No robustness / uncertainty status captured.");
    const evidenceWarningSummary = text(
      evidenceWarnings.summary,
      missingArtifactCount + " missing artifact(s), " + staleCount + " stale artifact(s), " + missingCount + " missing evidence item(s), " + warningCount + " bundle warning(s)"
    );
    return {
      audit,
      readiness,
      completeness,
      regulatoryCompleteness,
      trust,
      weather,
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
      verdict,
      topSummary,
      evidenceCompleteness,
      regulatoryDocCompleteness,
      weatherStatus,
      weatherSummary,
      robustnessStatus,
      robustnessSummary,
      evidenceWarningSummary,
    };
  }

  function renderSignals(summary) {
    const staleMissingMismatchCount = summary.staleCount + summary.missingArtifactCount + summary.mismatchCount;
    const cards = [
      statCard("Modeled mission status", summary.missionStatus, "", statusClass(summary.missionStatus)),
      statCard("Mission risk", summary.missionRisk, "", statusClass(summary.missionRisk)),
      statCard("Top limiting constraint", summary.topSummary),
      statCard("Regulatory readiness", summary.regulatoryState, "", statusClass(summary.regulatoryState)),
      statCard("Evidence completeness", summary.evidenceCompleteness, "Expected bundle artifacts", "status-neutral"),
      statCard("Regulatory documentation", summary.regulatoryDocCompleteness, "Documentation-only evidence fields", "status-neutral documentation-signal"),
      statCard("Weather fallback", summary.weatherStatus, summary.weatherSummary, statusClass(summary.weatherStatus)),
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
      section("Evidence Completeness", "Expected bundle artifacts and missing evidence counts.", [
        compactGrid([
          { label: "Artifact coverage", value: summary.evidenceCompleteness },
          { label: "Missing evidence", value: summary.missingCount },
          { label: "Bundle warnings", value: summary.warningCount },
        ]),
      ], [artifactNode(manifest, ["manifest_json"], "Manifest"), artifactNode(manifest, ["checksum_manifest"], "Checksums")], "evidence-completeness"),
      section("Trust / Defensibility", "Weather fallback, uncertainty, and model-context signals for audit review.", [
        compactGrid([
          { label: "Weather fallback", value: summary.weatherStatus, className: statusClass(summary.weatherStatus) },
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
    renderSignals(summary);
    renderArtifactLinks(manifest);
    renderOpenFirst(manifest);
    renderReviewSections(manifest, summary);
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
    robustness = trust.get("uncertainty_robustness_status") or {}
    evidence_warnings = trust.get("evidence_warning_summary") or {}
    missing_evidence = manifest.get("missing_evidence") or []
    bundle_warnings = manifest.get("bundle_warnings") or []
    review = manifest.get("operator_review") or {}

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
                "Modeled mission status", mission_status, class_name=_status_class(mission_status)
            ),
            _stat_card("Mission risk", mission_risk, class_name=_status_class(mission_risk)),
            _stat_card("Top limiting constraint", top_summary),
            _stat_card(
                "Regulatory readiness", regulatory_state, class_name=_status_class(regulatory_state)
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
                "Weather fallback", weather_status, weather_summary, _status_class(weather_status)
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
  <style>
    * {{ box-sizing: border-box; }}
    html {{ max-width: 100%; overflow-x: hidden; }}
    body {{
      margin: 0;
      max-width: 100%;
      overflow-x: hidden;
      color: #18212b;
      background: #f5f6f7;
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
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
    }}
    .topbar strong {{ display: block; font-size: 20px; }}
    .topbar span {{ color: #607080; }}
    .read-only-pill {{
      border: 1px solid #aab7c4;
      border-radius: 8px;
      color: #34495e;
      font-size: 12px;
      font-weight: 800;
      padding: 6px 9px;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    .dashboard-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.85fr);
      gap: 16px;
      align-items: start;
    }}
    .review-lead {{
      display: grid;
      gap: 12px;
    }}
    .verdict-band, .panel, .signal, .route-preview, .review-section {{
      background: #ffffff;
      border: 1px solid #d8dee7;
      border-radius: 8px;
    }}
    .verdict-band {{
      padding: 16px;
      border-left: 5px solid #0f5f9f;
    }}
    .eyebrow {{
      color: #607080;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{ margin: 8px 0 8px; font-size: 28px; line-height: 1.15; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }}
    .verdict-badge {{
      display: inline-flex;
      align-items: center;
      min-height: 31px;
      border-radius: 8px;
      padding: 4px 10px;
      font-weight: 800;
      border: 1px solid currentColor;
      font-size: 18px;
      vertical-align: middle;
    }}
    .status-good {{ color: #135c3a; background: #edf8f2; border-color: #8fc8a8; }}
    .status-review {{ color: #744400; background: #fff5dc; border-color: #d8ad49; }}
    .status-bad {{ color: #941919; background: #fff0f0; border-color: #db8f8f; }}
    .status-neutral {{ color: #425466; background: #f3f6f8; border-color: #ccd6df; }}
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
      padding: 12px;
      border-left: 4px solid #0f5f9f;
      background: #eef6fc;
      border-radius: 6px;
      border-top: 1px solid #c8dff1;
      border-right: 1px solid #c8dff1;
      border-bottom: 1px solid #c8dff1;
    }}
    .next-action p {{ margin: 6px 0 0; }}
    .signals {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 10px;
    }}
    .signal {{
      padding: 11px;
      min-height: 94px;
      overflow-wrap: anywhere;
      border-left: 4px solid #c9d4df;
    }}
    .signal.status-good {{ border-left-color: #2d8f5d; }}
    .signal.status-review {{ border-left-color: #c97f12; }}
    .signal.status-bad {{ border-left-color: #c94040; }}
    .signal.status-neutral {{ border-left-color: #9dadbb; }}
    .signal span {{ display: block; color: #607080; font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .signal strong {{ display: block; margin-top: 6px; font-size: 16px; line-height: 1.25; }}
    .signal p {{ margin: 6px 0 0; color: #425466; font-size: 12px; }}
    .warning-signal.status-review {{ border-left-color: #c97f12; background: #fff8e8; }}
    .warning-signal.status-bad {{ border-left-color: #c94040; background: #fff0f0; }}
    .warning-signal.status-good {{ border-left-color: #2d8f5d; background: #f3faf6; }}
    .documentation-signal {{ border-left-color: #8b9aaa !important; background: #f8fafb; }}
    .side-stack {{ display: grid; gap: 12px; }}
    .panel {{ padding: 14px; }}
    .boundary-list {{ margin: 0; padding-left: 18px; }}
    .boundary-list li {{ margin: 8px 0; }}
    .route-preview {{ margin: 0; padding: 14px; }}
    .route-preview img {{ display: block; width: 100%; height: auto; border-radius: 6px; border: 1px solid #d8dee7; }}
    .route-preview figcaption {{ margin-top: 8px; color: #607080; font-size: 13px; }}
    .route-missing {{ color: #607080; }}
    .quick-links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .quick-links a, .quick-links .unavailable {{
      border: 1px solid #c9d4df;
      border-radius: 8px;
      padding: 7px 9px;
      background: #f9fbfc;
      font-size: 13px;
      line-height: 1.2;
    }}
    .open-first {{
      border: 1px solid #0f5f9f;
      border-left: 5px solid #0f5f9f;
      border-radius: 8px;
      background: #eef6fc;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .open-first span {{
      display: block;
      color: #425466;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .open-first a {{
      display: inline-block;
      margin-top: 4px;
      font-size: 17px;
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
    .unavailable {{ color: #6f7d8a; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .meta-grid div {{ padding: 10px; background: #f9fbfc; border-radius: 6px; border: 1px solid #e3e8ee; }}
    .meta-grid span {{ display: block; color: #607080; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .meta-grid strong {{ display: block; margin-top: 4px; }}
    .review-sections {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .review-section {{ padding: 14px; min-height: 196px; overflow-wrap: anywhere; }}
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
    .section-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .section-links a, .section-links .unavailable {{
      border: 1px solid #c9d4df;
      border-radius: 8px;
      padding: 7px 9px;
      background: #f9fbfc;
      font-size: 13px;
    }}
    @media (max-width: 920px) {{
      .dashboard-grid {{ grid-template-columns: 1fr; }}
      .signals {{ grid-template-columns: repeat(3, minmax(150px, 1fr)); }}
      .review-sections {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 620px) {{
      main {{ padding: 16px; }}
      .topbar {{ padding: 14px 16px; align-items: flex-start; flex-direction: column; }}
      h1 {{ font-size: 24px; }}
      .verdict-badge {{ font-size: 16px; }}
      .signals, .meta-grid, .compact-grid, .review-sections {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div>
        <strong>ORBITAL Operator Review UI</strong>
        <span>Local read-only review surface for evidence bundles</span>
      </div>
      <span class="read-only-pill">Read-only demo / discovery aid</span>
    </header>
    <main>
      <section class="dashboard-grid" aria-label="Operator review dashboard">
        <div class="review-lead">
          <section class="verdict-band" aria-label="Mission verdict">
            <span class="eyebrow" data-field="mission-name">{escape(_text(mission_name))}</span>
            <h1>Mission Verdict: <span class="verdict-badge {_status_class(verdict["label"])}" data-field="verdict-label">{escape(verdict["label"])}</span></h1>
            <p data-field="verdict-meaning">{escape(verdict["meaning"])}</p>
            <p class="boundary-callout">Decision support only; the generated evidence bundle remains the source of truth.</p>
          </section>
          <div class="next-action">
            <strong>Next operator action</strong>
            <p data-field="next-action">{escape(verdict["next_action"])}</p>
          </div>
          <div class="signals" aria-label="Mission signals" data-signals>
            {cards}
          </div>
        </div>
        <aside class="side-stack" aria-label="Product boundary and bundle artifacts">
          <section class="panel">
            <h2>Product Boundary</h2>
            <ul class="boundary-list">
              <li>This UI is a local review surface for ORBITAL evidence bundles.</li>
              <li>It is a demo and discovery aid, not a full SaaS product.</li>
              <li>ORBITAL remains decision support, not approval, authorization, LAANC, legal advice, or operational clearance.</li>
              <li>Opening, clicking, or reviewing an artifact does not approve a mission.</li>
              <li>Review fields are documentation-only records.</li>
              <li>No accounts, databases, auth, editing workflows, live integrations, approvals, or signoff actions are provided.</li>
              <li>Markdown, JSON, CSV, KML, and checksum artifacts remain accessible outside this UI.</li>
            </ul>
          </section>
          {_route_preview(manifest)}
          <section class="panel" id="source-artifacts">
            <h2>Source Artifacts</h2>
            {_open_first(manifest)}
            <div class="quick-links" data-artifact-links>
              {_source_links(manifest)}
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
      <section class="review-sections" aria-label="Compact review sections" data-review-sections>
        {review_sections}
      </section>
    </main>
  </div>
  {loader_script}
</body>
</html>
"""
    return html
