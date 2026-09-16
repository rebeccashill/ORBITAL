from __future__ import annotations

REVIEW_UI_CSS = """:root {
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --radius-sm: 6px;
      --radius-md: 8px;
      --color-text: #17212b;
      --color-subtle: #425466;
      --color-muted: #607080;
      --color-page: #f2f4f7;
      --color-surface: #ffffff;
      --color-surface-soft: #f9fbfc;
      --color-border: #d8dee7;
      --color-border-soft: #e3e8ee;
      --color-accent: #0f5f9f;
      --status-good-fg: #0f5f3d;
      --status-good-bg: #edf8f2;
      --status-good-border: #8cc8a8;
      --status-review-fg: #704200;
      --status-review-bg: #fff5db;
      --status-review-border: #d6a13b;
      --status-bad-fg: #941919;
      --status-bad-bg: #fff0f0;
      --status-bad-border: #dc8d8d;
      --status-neutral-fg: #3f5061;
      --status-neutral-bg: #f4f7fa;
      --status-neutral-border: #cbd6df;
      --shadow-card: 0 1px 2px rgba(22, 34, 45, 0.06);
      --shadow-raised: 0 8px 24px rgba(20, 47, 72, 0.08);
      --shadow-focus: 0 6px 16px rgba(22, 34, 45, 0.16);
    }
    * { box-sizing: border-box; }
    html { max-width: 100%; overflow-x: hidden; }
    body {
      margin: 0;
      max-width: 100%;
      overflow-x: hidden;
      color: var(--color-text);
      background: var(--color-page);
      font-family: "Segoe UI", Arial, Helvetica, sans-serif;
      font-size: 16px;
      line-height: 1.45;
    }
    a { color: #0b5d95; font-weight: 700; text-decoration: none; }
    a:hover { text-decoration: underline; }
    a:focus-visible,
    button:focus-visible,
    .review-section:focus-visible {
      outline: 3px solid var(--color-accent);
      outline-offset: 3px;
    }
    .skip-link {
      position: absolute;
      top: -48px;
      left: 16px;
      z-index: 20;
      border-radius: var(--radius-sm);
      background: var(--color-surface);
      border: 2px solid var(--color-accent);
      color: var(--color-accent);
      padding: var(--space-2) 10px;
      box-shadow: var(--shadow-focus);
    }
    .skip-link:focus {
      top: 12px;
    }
    .shell { min-height: 100vh; }
    .topbar {
      background: var(--color-surface);
      border-bottom: 1px solid var(--color-border);
      border-top: 4px solid var(--color-accent);
      padding: 0 24px;
    }
    .topbar-inner {
      max-width: 1180px;
      margin: 0 auto;
      padding: 13px 0;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
    }
    .topbar strong { display: block; font-size: 20px; }
    .topbar span { color: var(--color-muted); }
    .topbar-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: var(--space-2);
      align-items: center;
    }
    .read-only-pill {
      border: 1px solid #aab7c4;
      border-radius: var(--radius-md);
      color: #34495e;
      font-size: 12px;
      font-weight: 800;
      padding: 6px 9px;
      text-transform: uppercase;
      white-space: nowrap;
      background: #f8fafc;
    }
    .print-button {
      border: 1px solid var(--color-accent);
      border-radius: var(--radius-md);
      background: var(--color-accent);
      color: var(--color-surface);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 800;
      min-height: 34px;
      padding: 6px 10px;
    }
    .print-button:hover { background: #0a4d82; }
    main { max-width: 1180px; margin: 0 auto; padding: 20px; }
    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 398px);
      gap: 16px;
      align-items: start;
    }
    .dashboard-left {
      display: grid;
      gap: 16px;
      min-width: 0;
    }
    .dashboard-primary {
      display: grid;
      gap: var(--space-3);
      min-width: 0;
    }
    .review-lead {
      display: grid;
      gap: var(--space-3);
    }
    .priority-stack {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--space-3);
      min-width: 0;
    }
    .priority-stack .why-verdict { grid-column: 1 / -1; }
    .dashboard-sidebar {
      display: grid;
      gap: var(--space-3);
      align-content: start;
      min-width: 0;
    }
    .supporting-evidence {
      display: grid;
      gap: 16px;
      margin-top: 0;
      min-width: 0;
    }
    .full-width-artifacts {
      margin-top: var(--space-2);
    }
    .supporting-main {
      display: grid;
      gap: var(--space-3);
      min-width: 0;
    }
    .verdict-band, .thirty-second-read, .panel, .signal, .route-preview, .review-section {
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-card);
    }
    .verdict-band {
      padding: 18px;
      border-left: 5px solid var(--color-accent);
      box-shadow: var(--shadow-raised);
    }
    .eyebrow {
      color: var(--color-muted);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    h1 {
      margin: 8px 0 8px;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
    }
    h2 { margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }
    h3 { margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }
    .verdict-badge {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      max-width: 100%;
      min-height: 31px;
      border-radius: var(--radius-md);
      padding: 4px 10px;
      font-weight: 800;
      border: 1px solid currentColor;
      font-size: 18px;
      vertical-align: middle;
      overflow-wrap: anywhere;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45);
    }
    .verdict-badge::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      flex: 0 0 auto;
    }
    .status-good { color: var(--status-good-fg); background: var(--status-good-bg); border-color: var(--status-good-border); }
    .status-review { color: var(--status-review-fg); background: var(--status-review-bg); border-color: var(--status-review-border); }
    .status-bad { color: var(--status-bad-fg); background: var(--status-bad-bg); border-color: var(--status-bad-border); }
    .status-neutral { color: var(--status-neutral-fg); background: var(--status-neutral-bg); border-color: var(--status-neutral-border); }
    .boundary-callout {
      margin: 12px 0 0;
      padding: 10px 11px;
      color: #263847;
      background: #f8fafb;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      font-size: 14px;
      font-weight: 700;
    }
    .next-action {
      margin: 0;
      padding: 14px 14px 14px 16px;
      border-left: 4px solid var(--color-accent);
      background: #eef6fb;
      border-radius: var(--radius-md);
      border-top: 1px solid #c8dff1;
      border-right: 1px solid #c8dff1;
      border-bottom: 1px solid #c8dff1;
      box-shadow: 0 1px 2px rgba(15, 95, 159, 0.06);
    }
    .next-action strong { display: block; font-size: 15px; }
    .next-action p { margin: 6px 0 0; }
    .thirty-second-read {
      display: grid;
      gap: 10px;
      padding: 14px;
      border-left: 5px solid #155e63;
      box-shadow: 0 6px 18px rgba(21, 94, 99, 0.08);
    }
    .thirty-second-read header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: var(--space-2) 12px;
      align-items: baseline;
    }
    .thirty-second-read header span {
      color: #155e63;
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .thirty-second-read header strong {
      color: var(--color-subtle);
      font-size: 13px;
    }
    .read-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--space-2);
    }
    .read-item {
      min-height: 92px;
      border: 1px solid var(--color-border);
      border-left: 4px solid #9dadbb;
      border-radius: var(--radius-md);
      background: var(--color-surface-soft);
      padding: 10px;
      overflow-wrap: anywhere;
    }
    .read-item.read-action { grid-column: span 3; }
    .read-item.signal-top { border-left-color: var(--color-accent); background: #f5fbff; }
    .read-item.status-good { border-left-color: #2d8f5d; }
    .read-item.status-review { border-left-color: #c97f12; }
    .read-item.status-bad { border-left-color: #c94040; }
    .read-item span {
      display: block;
      color: var(--color-muted);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .read-item strong {
      display: block;
      margin-top: 5px;
      color: var(--color-text);
      font-size: 15px;
      line-height: 1.22;
    }
    .read-item p {
      margin: 6px 0 0;
      color: var(--color-subtle);
      font-size: 12px;
    }
    .freshness-strip {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--space-2);
    }
    .freshness-strip article {
      min-height: 86px;
      border: 1px solid var(--color-border);
      border-left: 4px solid #7d8b99;
      border-radius: var(--radius-md);
      background: var(--color-surface);
      padding: 11px;
      box-shadow: var(--shadow-card);
      overflow-wrap: anywhere;
    }
    .freshness-strip span {
      display: block;
      color: var(--color-muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .freshness-strip strong {
      display: block;
      margin-top: 5px;
      font-size: 15px;
      line-height: 1.2;
    }
    .freshness-strip small {
      display: block;
      margin-top: 5px;
      color: var(--color-subtle);
      font-size: 12px;
    }
    .review-order {
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-left: 5px solid #263847;
      border-radius: var(--radius-md);
      padding: 13px;
      box-shadow: var(--shadow-card);
    }
    .review-order > span {
      display: block;
      color: var(--color-muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .review-order p {
      margin: 4px 0 10px;
      color: #263847;
      font-weight: 800;
    }
    .review-order ol {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
      gap: var(--space-2);
    }
    .review-order a {
      display: grid;
      gap: 3px;
      height: 100%;
      min-height: 92px;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      background: var(--color-surface-soft);
      color: var(--color-text);
      padding: 9px;
    }
    .review-order a:hover {
      background: #eef6fb;
      border-color: #8fb8d4;
      text-decoration: none;
    }
    .review-order a span {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      display: inline-grid;
      place-items: center;
      color: var(--color-surface);
      background: var(--color-accent);
      font-size: 12px;
      font-weight: 800;
    }
    .review-order a strong {
      display: block;
      font-size: 14px;
      line-height: 1.2;
    }
    .review-order a small {
      color: #526578;
      font-size: 12px;
      line-height: 1.25;
    }
    .why-verdict {
      padding: 14px;
      border-left: 4px solid #7255a1;
      background: #fbf9ff;
    }
    .why-verdict h2 { margin-bottom: 6px; }
    .why-verdict p { margin: 0 0 10px; color: var(--color-subtle); }
    .signals {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .signal {
      padding: 12px;
      min-height: 98px;
      overflow-wrap: anywhere;
      border-left: 4px solid #c9d4df;
    }
    .signal.decision-signal {
      min-height: 116px;
      border-top-color: #cad6df;
      box-shadow: 0 5px 16px rgba(22, 34, 45, 0.07);
    }
    .signal.signal-top { border-left-color: var(--color-accent); background: #f9fcfe; }
    .signal.status-good { border-left-color: #2d8f5d; }
    .signal.status-review { border-left-color: #c97f12; }
    .signal.status-bad { border-left-color: #c94040; }
    .signal.status-neutral { border-left-color: #9dadbb; }
    .signal span { display: block; color: var(--color-muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }
    .signal strong {
      display: block;
      margin-top: 6px;
      font-size: 16px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .signal p {
      margin: 6px 0 0;
      color: var(--color-subtle);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .warning-signal.status-review { border-left-color: #c97f12; background: #fff8e8; }
    .warning-signal.status-bad { border-left-color: #c94040; background: var(--status-bad-bg); }
    .warning-signal.status-good { border-left-color: #2d8f5d; background: #f3faf6; }
    .documentation-signal { border-left-color: #8b9aaa !important; background: #f8fafb; }
    .side-stack {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: var(--space-3);
      align-items: start;
    }
    .dashboard-sidebar .side-stack {
      grid-template-columns: 1fr;
    }
    .panel { padding: 15px; }
    .boundary-list { margin: 0; padding-left: 18px; }
    .dashboard-sidebar .boundary-list {
      columns: 1;
    }
    .side-stack .product-boundary-panel {
      grid-column: span 2;
    }
    .side-stack .product-boundary-panel .boundary-list {
      columns: 2;
      column-gap: 20px;
    }
    .boundary-list li { margin: 8px 0; }
    .route-preview { margin: 0; padding: 14px; }
    .route-preview img { display: block; width: 100%; height: auto; border-radius: var(--radius-sm); border: 1px solid var(--color-border); }
    .route-preview figcaption { margin-top: var(--space-2); color: var(--color-muted); font-size: 13px; }
    .route-missing { color: var(--color-muted); }
    .quick-links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
    .raw-evidence-groups {
      display: grid;
      gap: 11px;
      align-items: start;
    }
    .quick-link-group {
      display: grid;
      gap: 7px;
      align-content: start;
      align-self: start;
      min-width: 0;
    }
    .quick-link-group h3 {
      margin: 0;
      color: var(--color-subtle);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .artifact-link {
      border: 1px solid #c9d4df;
      border-radius: var(--radius-md);
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
    }
    a.artifact-link:hover {
      background: #eef6fb;
      border-color: #8fb8d4;
      box-shadow: 0 2px 8px rgba(15, 95, 159, 0.12);
      text-decoration: none;
    }
    .artifact-link span { min-width: 0; overflow-wrap: anywhere; }
    .artifact-link small {
      color: #526578;
      background: #eef2f6;
      border: 1px solid #d6dee7;
      border-radius: 999px;
      flex: 0 0 auto;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      text-transform: uppercase;
    }
    .artifact-unavailable {
      background: #f5f6f8;
      border-style: dashed;
      color: #6c7885;
    }
    .open-first {
      border: 1px solid var(--color-accent);
      border-left: 5px solid var(--color-accent);
      border-radius: var(--radius-md);
      background: #eef6fc;
      padding: 13px;
      margin-bottom: 12px;
      box-shadow: 0 3px 12px rgba(15, 95, 159, 0.1);
    }
    .open-first > span {
      display: block;
      color: var(--color-subtle);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .open-first a {
      display: flex;
      margin-top: 4px;
      font-size: 17px;
      background: var(--color-surface);
    }
    .open-first p {
      margin: 6px 0 0;
      color: var(--color-subtle);
      font-size: 13px;
    }
    .loading-status {
      border: 1px solid #c9d4df;
      border-radius: var(--radius-md);
      margin: 12px 0 0;
      padding: 10px;
      font-size: 13px;
      font-weight: 700;
    }
    .loading-status.status-good { background: var(--status-good-bg); border-color: #8fc8a8; color: #135c3a; }
    .loading-status.status-review { background: #fff5dc; border-color: #d8ad49; color: #744400; }
    .loading-status.status-bad { background: var(--status-bad-bg); border-color: #db8f8f; color: var(--status-bad-fg); }
    .unavailable { color: #6f7d8a; }
    .meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .meta-grid div { padding: 10px; background: var(--color-surface-soft); border-radius: var(--radius-sm); border: 1px solid var(--color-border-soft); }
    .meta-grid span { display: block; color: var(--color-muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }
    .meta-grid strong {
      display: block;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .review-sections {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--space-3);
      margin-top: 16px;
      align-items: start;
    }
    .dashboard-review-sections {
      grid-template-columns: 1fr;
      margin-top: 0;
    }
    .review-intro-row,
    .review-column-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--space-3);
      align-items: start;
    }
    .review-column {
      display: grid;
      gap: 10px;
      align-content: start;
      min-width: 0;
    }
    .review-section {
      padding: 12px;
      min-height: 176px;
      overflow-wrap: anywhere;
      scroll-margin-top: 18px;
    }
    #evidence-completeness {
      min-height: 0;
    }
    .review-section h2 { font-size: 17px; margin-bottom: 6px; }
    .review-section p { margin: 0 0 9px; color: var(--color-subtle); font-size: 13px; line-height: 1.35; }
    .compact-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }
    .compact-grid div {
      border: 1px solid var(--color-border-soft);
      border-radius: var(--radius-sm);
      background: var(--color-surface-soft);
      padding: 7px;
      min-height: 52px;
    }
    .compact-grid span {
      display: block;
      color: var(--color-muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .compact-grid strong {
      display: block;
      margin-top: 3px;
      font-size: 14px;
      line-height: 1.2;
    }
    .compact-grid strong.status-good,
    .compact-grid strong.status-review,
    .compact-grid strong.status-bad,
    .compact-grid strong.status-neutral {
      border-radius: var(--radius-sm);
      padding: 3px 6px;
      width: fit-content;
    }
    .compact-note { margin-top: 8px !important; }
    .compact-list {
      margin: 6px 0 0;
      padding-left: 16px;
      color: var(--color-subtle);
      font-size: 12px;
      line-height: 1.3;
    }
    .evidence-detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 5px;
      margin-top: 6px;
    }
    .evidence-disclosure {
      margin-top: 6px;
      border: 1px solid var(--color-border-soft);
      border-radius: var(--radius-sm);
      background: var(--color-surface-soft);
    }
    .evidence-disclosure summary {
      cursor: pointer;
      padding: 6px 8px;
      color: var(--color-accent);
      font-size: 12px;
      font-weight: 800;
    }
    .evidence-disclosure .evidence-detail-grid {
      padding: 0 6px 6px;
    }
    .evidence-disclosure > .compact-note {
      margin: 0 8px 6px !important;
    }
    .evidence-disclosure > .compact-list {
      margin: 0 8px 8px;
    }
    .evidence-detail-row {
      display: grid;
      grid-template-columns: minmax(78px, max-content) 1fr;
      gap: 6px;
      align-items: baseline;
      border: 1px solid var(--color-border-soft);
      border-radius: var(--radius-sm);
      background: var(--color-surface-soft);
      padding: 5px 6px;
      min-width: 0;
    }
    .evidence-detail-row.wide { grid-column: 1 / -1; }
    .evidence-detail-row span {
      color: var(--color-muted);
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .evidence-detail-row strong {
      min-width: 0;
      color: var(--color-text);
      font-size: 12px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }
    .assumption-list {
      display: grid;
      gap: var(--space-2);
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .assumption-list li {
      border: 1px solid var(--color-border-soft);
      border-radius: var(--radius-sm);
      background: var(--color-surface-soft);
      padding: 9px;
    }
    .assumption-list strong,
    .assumption-list span,
    .assumption-list em {
      display: block;
      overflow-wrap: anywhere;
    }
    .assumption-list strong { font-size: 14px; }
    .assumption-list span { margin-top: 4px; color: var(--color-subtle); font-size: 13px; }
    .assumption-list em { margin-top: 5px; color: #5d4d1e; font-size: 12px; font-style: normal; font-weight: 700; }
    .freshness-list {
      display: grid;
      gap: var(--space-2);
    }
    .freshness-list div {
      border: 1px solid var(--color-border-soft);
      border-radius: var(--radius-sm);
      background: var(--color-surface-soft);
      padding: 9px;
    }
    .freshness-list span,
    .freshness-list strong,
    .freshness-list small {
      display: block;
      overflow-wrap: anywhere;
    }
    .freshness-list span { color: var(--color-muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }
    .freshness-list strong { margin-top: 4px; border-radius: var(--radius-sm); padding: 3px 6px; width: fit-content; }
    .freshness-list small { margin-top: 4px; color: var(--color-subtle); font-size: 12px; }
    .section-links {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--space-2);
      margin-top: 8px;
    }
    .side-stack [data-artifact-freshness],
    .side-stack #source-artifacts,
    .side-stack #raw-evidence-links {
      grid-column: span 2;
    }
    .side-stack .quick-links { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .side-stack .raw-evidence-groups {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .side-stack .raw-evidence-groups .quick-links { grid-template-columns: 1fr; }
    .dashboard-sidebar .side-stack [data-artifact-freshness],
    .dashboard-sidebar .side-stack #source-artifacts,
    .dashboard-sidebar .side-stack #raw-evidence-links {
      grid-column: auto;
    }
    .dashboard-sidebar .side-stack .quick-links,
    .dashboard-sidebar .side-stack .raw-evidence-groups {
      grid-template-columns: 1fr;
    }
    .dashboard-sidebar #source-artifacts .quick-links {
      gap: 6px;
    }
    .dashboard-sidebar #source-artifacts .artifact-link {
      min-height: 34px;
      padding: 6px 8px;
      font-size: 12px;
    }
    .full-width-artifacts .raw-evidence-groups {
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    }
    .full-width-artifacts .quick-links {
      grid-template-columns: 1fr;
    }
    .evidence-readiness-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .evidence-readiness-grid div { min-height: 48px; }
    #trust-defensibility .compact-grid div:nth-child(n+3) { grid-column: span 2; min-height: 0; }
    #artifact-navigation .section-links { grid-template-columns: 1fr; }
    .section-links .artifact-link { font-size: 13px; }
    @media (max-width: 1100px) {
      .side-stack { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .side-stack [data-artifact-freshness],
      .side-stack #source-artifacts,
      .side-stack #raw-evidence-links {
        grid-column: span 2;
      }
    }
    @media (max-width: 920px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }
      .side-stack { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .side-stack .product-boundary-panel,
      .side-stack [data-artifact-freshness],
      .side-stack #source-artifacts,
      .side-stack #raw-evidence-links {
        grid-column: span 2;
      }
      .review-order ol { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .signals { grid-template-columns: repeat(3, minmax(150px, 1fr)); }
      .review-sections { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .review-intro-row,
      .review-column-grid {
        grid-template-columns: 1fr;
      }
      .full-width-artifacts .raw-evidence-groups {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 620px) {
      main { padding: 12px; }
      .topbar { padding: 0 16px; }
      .topbar-inner { padding: 10px 0; align-items: flex-start; flex-direction: column; gap: var(--space-2); }
      .topbar strong { font-size: 18px; }
      .topbar-inner > div:first-child span { font-size: 13px; }
      .topbar-actions { gap: 6px; }
      .print-button { display: none; }
      main,
      .dashboard-grid,
      .dashboard-left,
      .dashboard-sidebar,
      .review-lead,
      .priority-stack,
      .dashboard-context,
      .supporting-evidence,
      .full-width-artifacts,
      .supporting-main,
      .side-stack,
      .verdict-band,
      .thirty-second-read,
      .next-action,
      .panel,
      .route-preview,
      .signal,
      .review-section {
        min-width: 0;
        max-width: 100%;
      }
      .review-lead { gap: var(--space-2); }
      h1 { display: block; font-size: 23px; margin: 6px 0; }
      .verdict-band { padding: 14px; }
      .verdict-band [data-field="verdict-meaning"] {
        margin: 8px 0 0;
        font-size: 14px;
        line-height: 1.3;
      }
      .boundary-callout { display: none; }
      .verdict-badge { display: flex; margin-top: var(--space-2); width: fit-content; font-size: 16px; }
      .thirty-second-read { padding: 10px; gap: 7px; }
      .thirty-second-read header { gap: 3px; }
      .read-grid { gap: 6px; }
      .read-item { min-height: 0; padding: 8px; }
      .read-item strong { font-size: 14px; }
      .read-item p { margin-top: 4px; font-size: 11px; line-height: 1.2; }
      .signals, .priority-stack, .meta-grid, .compact-grid, .review-sections, .quick-links, .section-links, .review-order ol, .freshness-strip, .read-grid, .side-stack, .raw-evidence-groups { grid-template-columns: 1fr; }
      .completeness-grid,
      #evidence-completeness .section-links {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .read-item.read-action { grid-column: auto; }
      .priority-stack .why-verdict { grid-column: auto; }
      .side-stack #source-artifacts,
      .side-stack .product-boundary-panel,
      .side-stack [data-artifact-freshness],
      .side-stack #raw-evidence-links {
        grid-column: auto;
      }
      .side-stack .product-boundary-panel .boundary-list { columns: 1; }
      .evidence-detail-grid { grid-template-columns: 1fr; }
      .evidence-detail-row,
      .evidence-detail-row.wide { grid-column: auto; grid-template-columns: 1fr; gap: 2px; }
      #trust-defensibility .compact-grid div:nth-child(n+3) { grid-column: auto; }
    }
    @media print {
      @page {
        size: letter;
        margin: 0.35in;
      }
      body {
        background: var(--color-surface);
        color: #111827;
        font-size: 10.5px;
        line-height: 1.25;
      }
      .shell {
        min-height: auto;
      }
      .skip-link,
      .print-button,
      .loading-status,
      script {
        display: none !important;
      }
      .topbar {
        position: static;
        border-top: 0;
        border-bottom: 1px solid var(--color-border);
        padding: 0 0 8px;
        margin-bottom: 10px;
      }
      .topbar-inner {
        display: block;
        max-width: none;
        padding: 0;
      }
      .topbar span {
        margin-top: 2px;
      }
      main {
        max-width: none;
        padding: 0;
      }
      .dashboard-grid {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .dashboard-left,
      .dashboard-primary {
        display: contents;
      }
      .review-lead { order: 1; }
      .dashboard-context { order: 2; }
      .signals { order: 3; }
      .dashboard-sidebar {
        order: 5;
        display: block;
        gap: var(--space-2);
      }
      .dashboard-sidebar .side-stack {
        display: block;
        margin-top: var(--space-2);
      }
      .supporting-evidence {
        order: 4;
        display: grid;
        gap: var(--space-2);
        margin-top: 10px;
      }
      .review-lead,
      .priority-stack,
      .supporting-main {
        display: grid;
        gap: var(--space-2);
      }
      .priority-stack {
        grid-template-columns: 1fr 1fr;
      }
      .priority-stack .why-verdict {
        grid-column: span 2;
      }
      .full-width-artifacts {
        margin-top: var(--space-2);
      }
      .full-width-artifacts .raw-evidence-groups {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 6px;
      }
      .review-sections {
        display: block;
        column-count: 2;
        column-gap: var(--space-2);
        column-fill: balance;
      }
      .review-intro-row,
      .review-column-grid,
      .review-column {
        display: contents;
      }
      .signals {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: var(--space-2);
      }
      .compact-grid,
      .meta-grid,
      .freshness-strip,
      .read-grid,
      .review-order ol {
        grid-template-columns: 1fr 1fr;
        gap: 6px;
      }
      .read-item.read-action {
        grid-column: span 2;
      }
      .verdict-band,
      .thirty-second-read,
      .panel,
      .signal,
      .route-preview,
      .review-section,
      .next-action,
      .review-order {
        break-inside: avoid-page;
        box-shadow: none;
      }
      .verdict-band,
      .thirty-second-read,
      .panel,
      .signal,
      .route-preview,
      .review-section,
      .review-order {
        padding: 9px;
      }
      .review-section {
        display: inline-block;
        min-height: 0;
        width: 100%;
        margin: 0 0 6px;
      }
      .dashboard-sidebar > .panel,
      .dashboard-sidebar .side-stack > .panel,
      .dashboard-sidebar .side-stack > .route-preview {
        margin-bottom: var(--space-2);
      }
      .artifact-link {
        min-height: 0;
        padding: 5px 6px;
        font-size: 9.5px;
      }
      #source-artifacts,
      #raw-evidence-links {
        break-inside: auto;
      }
      .dashboard-sidebar .panel,
      .dashboard-sidebar .route-preview,
      .full-width-artifacts {
        break-inside: auto;
      }
      .product-boundary-panel,
      [data-artifact-freshness],
      .full-width-artifacts {
        break-inside: avoid-page;
      }
      .full-width-artifacts {
        break-before: page;
      }
      .product-boundary-panel .boundary-list {
        columns: 2;
        column-gap: 18px;
        margin: 0;
        padding-left: 15px;
      }
      .product-boundary-panel .boundary-list li {
        margin: 3px 0;
      }
      .assumption-list li,
      .quick-link-group,
      .artifact-link {
        break-inside: avoid-page;
      }
      #source-artifacts .quick-links {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 5px;
      }
      #raw-evidence-links .quick-link-group {
        break-inside: avoid-page;
      }
      h1 {
        font-size: 20px;
      }
      h2 {
        font-size: 14px;
        margin-bottom: 5px;
      }
      .review-section p,
      .compact-note,
      .signal p,
      .read-item p,
      .freshness-strip small {
        font-size: 10px;
      }
      .freshness-list {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 5px;
      }
      .freshness-list div {
        break-inside: avoid-page;
        padding: 6px;
      }
      .route-preview img {
        max-height: 180px;
        object-fit: contain;
      }
      a[href]::after {
        content: none;
      }
    }
"""


def operator_review_ui_css() -> str:
    return REVIEW_UI_CSS
