from __future__ import annotations

import json
from typing import Any, Mapping


def operator_review_manifest_loader_script(manifest: Mapping[str, Any]) -> str:
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

  function evidenceDetailDisclosure(items) {
    const details = document.createElement("details");
    details.className = "evidence-disclosure";
    const summary = document.createElement("summary");
    summary.textContent = "Source, freshness, and provenance details";
    const grid = document.createElement("div");
    grid.className = "evidence-detail-grid";
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "evidence-detail-row" + (item.wide ? " wide" : "");
      const label = document.createElement("span");
      label.textContent = item.label;
      const value = document.createElement("strong");
      value.textContent = text(item.value);
      row.append(label, value);
      grid.appendChild(row);
    });
    details.append(summary, grid);
    return details;
  }

  function disclosureNode(summaryText, nodes) {
    const details = document.createElement("details");
    details.className = "evidence-disclosure";
    const summary = document.createElement("summary");
    summary.textContent = summaryText;
    details.append(summary, ...nodes);
    return details;
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
    const cards = [
      statCard("Modeled mission status", summary.missionStatus, "", "decision-signal " + statusClass(summary.missionStatus)),
      statCard("Mission risk", summary.missionRisk, "", "decision-signal " + statusClass(summary.missionRisk)),
      statCard("Top limiting constraint", summary.topSummary, "", "decision-signal signal-top"),
      statCard("Regulatory readiness", summary.regulatoryState, "", "decision-signal " + statusClass(summary.regulatoryState)),
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
    const bundleCompleteness = objectOr(manifest.bundle_completeness || manifest.artifact_completeness);
    const missingRegulatory = arrayOr(regulatoryStatus.missing);
    const pendingCount = intValue(approvalChecklist.pending_count, intValue(approvalChecklist.item_count, 0));
    const staleMissingMismatchCount = summary.staleCount + summary.missingArtifactCount + summary.mismatchCount;
    const artifactsPresent = intValue(bundleCompleteness.present_artifacts, 0) + " / " + intValue(bundleCompleteness.total_artifacts, 0);

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

    const loadingStatus = document.createElement("p");
    loadingStatus.className = "loading-status status-neutral";
    loadingStatus.setAttribute("data-manifest-status", "");
    loadingStatus.textContent = "Preparing review data from embedded snapshot or manifest.json...";

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
            { label: "Regulatory provenance", value: statusLabel(regulatoryProvenance.status), className: statusClass(regulatoryProvenance.status) },
            { label: "Checksum evidence", value: statusLabel(checksumReadiness.status), className: statusClass(checksumReadiness.status) },
          ]);
          grid.classList.add("evidence-readiness-grid");
          return grid;
        })(),
        evidenceDetailDisclosure([
          { label: "Weather source", value: weatherReadiness.source },
          { label: "Weather timestamp", value: weatherReadiness.timestamp_utc },
          { label: "Weather freshness", value: weatherReadiness.freshness_status },
          { label: "Authority", value: regulatoryProvenance.authority },
          { label: "Date checked", value: regulatoryProvenance.date_checked_utc },
          { label: "Expiration", value: regulatoryProvenance.expiration_date },
          { label: "Operator confirmation", value: regulatoryProvenance.operator_confirmation_status },
          { label: "Weather action", value: shortText(weatherReadiness.operator_action, "Confirm current weather before release.", 110), wide: true },
        ]),
        (() => {
          const note = document.createElement("p");
          note.className = "compact-note";
          note.textContent = "Live weather and regulatory hooks are documentation-only unless verified outside ORBITAL.";
          return note;
        })(),
      ], [artifactNode(manifest, ["weather_snapshot"], "Weather snapshot"), artifactNode(manifest, ["regulatory_readiness_markdown"], "Regulatory report")], "live-evidence-readiness"),
      section("Evidence Completeness", "Expected bundle artifacts and missing evidence counts.", [
        (() => {
          const grid = compactGrid([
            { label: "Artifact coverage", value: pct(bundleCompleteness.score) },
            { label: "Artifacts present", value: artifactsPresent },
            { label: "Missing evidence", value: summary.missingCount },
            { label: "Bundle warnings", value: summary.warningCount },
          ]);
          grid.classList.add("completeness-grid");
          return grid;
        })(),
      ], [artifactNode(manifest, ["manifest_json"], "Manifest"), artifactNode(manifest, ["checksum_manifest"], "Checksums")], "evidence-completeness"),
      section("Trust / Defensibility", "Weather evidence, uncertainty, and model-context signals for audit review.", [
        compactGrid([
          { label: "Weather evidence", value: summary.weatherStatus, className: statusClass(summary.weatherStatus) },
          { label: "Robustness", value: summary.robustnessStatus, className: statusClass(summary.robustnessStatus) },
        ]),
        evidenceDetailDisclosure([
          { label: "Weather note", value: shortText(summary.weatherSummary), wide: true },
          { label: "Robustness note", value: shortText(summary.robustnessSummary), wide: true },
          { label: "Sample note", value: trustNote.textContent, wide: true },
        ]),
      ], [artifactNode(manifest, ["operator_dashboard"], "Dashboard MD")], "trust-defensibility"),
      section("Warnings", "Stale, missing, mismatched, or otherwise review-required evidence signals.", [
        compactGrid([
          { label: "Stale artifacts", value: summary.staleCount },
          { label: "Missing artifacts", value: summary.missingArtifactCount },
          { label: "Mismatched artifacts", value: summary.mismatchCount },
          { label: "Warning total", value: summary.warningCount, className: statusClass(summary.warningCount === 0 ? "clear" : "review_required") },
        ]),
        disclosureNode("Warning details", [warningsNote, warningList]),
      ], [artifactNode(manifest, ["checksum_manifest"], "Checksum manifest")], "warnings"),
      section("Data Loading", "Manifest load path and runtime read-only status.", [
        compactGrid([
          { label: "Primary source", value: "outputs/bvlos_powerline_inspection/operator_evidence_bundle/manifest.json" },
          { label: "Runtime target", value: "manifest.json" },
          { label: "Writes", value: "read-only UI; no bundle mutation" },
          { label: "Storage", value: "no backend database required" },
        ]),
        loadingStatus,
      ], [], "data-loading"),
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

    function reviewColumn(items) {
      const column = document.createElement("div");
      column.className = "review-column";
      items.forEach((item) => column.appendChild(item.cloneNode(true)));
      return column;
    }

    function reviewLayout() {
      const intro = document.createElement("div");
      intro.className = "review-intro-row";
      [sections[0], sections[1]].forEach((item) => intro.appendChild(item.cloneNode(true)));

      const columns = document.createElement("div");
      columns.className = "review-column-grid";
      columns.appendChild(reviewColumn([sections[2], sections[6], sections[8]]));
      columns.appendChild(reviewColumn([sections[3], sections[4], sections[5], sections[7]]));
      return [intro, columns];
    }

    document.querySelectorAll("[data-review-sections]").forEach((node) => replaceChildren(node, reviewLayout()));
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
    if (window.location.protocol === "file:") {
      try {
        renderManifest(fallbackManifest(), "Loaded embedded manifest snapshot. Run `python -m mission_framework.cli serve-ui` when you want live manifest.json refresh.", "status-neutral");
      } catch (fallbackError) {
        setStatusText("Embedded manifest snapshot is unavailable. Static fallback text remains visible.", "status-bad");
      }
      return;
    }
    try {
      const response = await fetch(manifestUrl, { cache: "no-store" });
      if (!response.ok) {
        throw new Error("manifest.json returned HTTP " + response.status);
      }
      const manifest = await response.json();
      renderManifest(manifest, "Loaded primary data from manifest.json. No backend database is required.", "status-good");
    } catch (error) {
      try {
        console.debug("manifest.json could not be loaded or parsed", error);
        renderManifest(fallbackManifest(), "Using embedded fallback snapshot; primary manifest.json was unavailable. Run serve-ui for live disk refresh.", "status-neutral");
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
