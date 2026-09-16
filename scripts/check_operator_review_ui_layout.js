#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { pathToFileURL } = require("url");

const RESPONSIVE_VIEWPORTS = [
  { name: "desktop-1366", width: 1366, height: 768, kind: "desktop" },
  { name: "desktop-1440", width: 1440, height: 900, kind: "desktop" },
  { name: "desktop-1920", width: 1920, height: 1080, kind: "desktop" },
  { name: "tablet", width: 768, height: 1024, kind: "tablet" },
  { name: "mobile", width: 390, height: 844, kind: "mobile" },
];

function parseArgs(argv) {
  const args = {
    bundle: "outputs/bvlos_powerline_inspection/operator_evidence_bundle",
    outdir: path.join("tmp", "operator_review_ui_layout"),
    keepArtifacts: false,
    json: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--bundle") {
      args.bundle = argv[++index];
    } else if (token === "--html") {
      args.html = argv[++index];
    } else if (token === "--outdir") {
      args.outdir = argv[++index];
    } else if (token === "--keep-artifacts") {
      args.keepArtifacts = true;
    } else if (token === "--json") {
      args.json = true;
    } else if (token === "--help" || token === "-h") {
      args.help = true;
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }
  return args;
}

function usage() {
  return [
    "Usage: node scripts/check_operator_review_ui_layout.js [options]",
    "",
    "Options:",
    "  --bundle <dir>       Evidence bundle directory containing operator_review_ui.html",
    "  --html <file>        Direct path to operator_review_ui.html",
    "  --outdir <dir>       Where to write screenshots and print PDF",
    "  --keep-artifacts     Keep screenshots/PDF after a passing run",
    "  --json               Emit machine-readable JSON summary",
  ].join("\n");
}

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (firstError) {
    const candidates = [
      process.env.ORBITAL_PLAYWRIGHT_NODE_MODULES,
      process.env.NODE_PATH,
      path.join(
        os.homedir(),
        ".cache",
        "codex-runtimes",
        "codex-primary-runtime",
        "dependencies",
        "node",
        "node_modules",
      ),
    ]
      .filter(Boolean)
      .flatMap((entry) => String(entry).split(path.delimiter))
      .filter(Boolean);

    for (const candidate of candidates) {
      try {
        return require(path.join(candidate, "playwright"));
      } catch (_err) {
        // Try the next location.
      }
    }
    throw new Error(
      "Playwright is required for UI layout checks. Install it with `npm install playwright` " +
        "or set ORBITAL_PLAYWRIGHT_NODE_MODULES to a node_modules directory containing Playwright. " +
        `Original error: ${firstError.message}`,
    );
  }
}

function assertLayout(condition, message, details = {}) {
  if (!condition) {
    const error = new Error(message);
    error.details = details;
    throw error;
  }
}

function rectOverlap(a, b) {
  const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  return { x, y };
}

async function launchBrowser(chromium) {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch (_err) {
    return chromium.launch({ headless: true });
  }
}

async function collectLayout(page) {
  return page.evaluate(() => {
    const selectorIds = [
      "mission-verdict",
      "live-evidence-readiness",
      "evidence-completeness",
      "trust-defensibility",
      "warnings",
      "artifact-navigation",
    ];
    const rectFor = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        id: element.id || element.getAttribute("data-layout-name") || element.tagName,
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    };
    const visible = selectorIds.map((id) => {
      const element = document.getElementById(id);
      return {
        id,
        exists: Boolean(element),
        visible: Boolean(element && element.getClientRects().length),
        text: element ? element.textContent.trim().replace(/\s+/g, " ").slice(0, 80) : "",
      };
    });
    const reviewSections = Array.from(
      document.querySelectorAll(".dashboard-review-sections .review-section"),
    ).map(rectFor);
    const reviewColumns = Array.from(document.querySelectorAll(".review-column")).map((column) =>
      Array.from(column.querySelectorAll(":scope > .review-section")).map(rectFor),
    );
    const live = document.getElementById("live-evidence-readiness");
    const completeness = document.getElementById("evidence-completeness");
    const trust = document.getElementById("trust-defensibility");
    const warnings = document.getElementById("warnings");
    const reviewStack = document.querySelector(".dashboard-review-sections");
    const freshnessList = document.querySelector(".freshness-list");
    return {
      visible,
      reviewSections,
      reviewColumns,
      live: live ? rectFor(live) : null,
      completeness: completeness ? rectFor(completeness) : null,
      densityCards: {
        live: live ? rectFor(live) : null,
        completeness: completeness ? rectFor(completeness) : null,
        trust: trust ? rectFor(trust) : null,
        warnings: warnings ? rectFor(warnings) : null,
      },
      reviewDisplay: reviewStack ? getComputedStyle(reviewStack).display : null,
      reviewGridColumns: reviewStack ? getComputedStyle(reviewStack).gridTemplateColumns : null,
      freshnessColumns: freshnessList ? getComputedStyle(freshnessList).gridTemplateColumns : null,
    };
  });
}

async function collectAccessibility(page) {
  return page.evaluate(() => {
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const alphaFor = (color) => {
      const match = color.match(/^rgba?\((.*)\)$/);
      if (!match) {
        return color === "transparent" ? 0 : 1;
      }
      const parts = match[1].replace(/\//g, " ").replace(/,/g, " ").split(/\s+/).filter(Boolean);
      if (parts.length < 4) {
        return 1;
      }
      const alpha = parts[3].endsWith("%")
        ? Number(parts[3].slice(0, -1)) / 100
        : Number(parts[3]);
      return Number.isFinite(alpha) ? alpha : 1;
    };
    const effectiveBackground = (element) => {
      let current = element;
      while (current) {
        const backgroundColor = getComputedStyle(current).backgroundColor;
        if (alphaFor(backgroundColor) > 0) {
          return backgroundColor;
        }
        current = current.parentElement;
      }
      return "rgb(255, 255, 255)";
    };
    const elementSummary = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName,
        id: element.id || "",
        className: element.className || "",
        text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
        href: element.getAttribute("href") || "",
        tabindex: element.getAttribute("tabindex") || "",
        visible: isVisible(element),
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    };
    const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(
      (heading) => ({
        level: Number(heading.tagName.slice(1)),
        text: heading.textContent.trim().replace(/\s+/g, " "),
        id: heading.id || "",
      }),
    );
    const focusables = Array.from(
      document.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])'),
    )
      .filter(isVisible)
      .map(elementSummary);
    const contrastSelectors = [
      "body",
      ".verdict-band",
      ".artifact-link",
      ".status-review",
      ".status-good",
      ".status-bad",
      ".status-neutral",
      ".read-only-pill",
      ".print-button",
    ];
    const contrastChecks = contrastSelectors.map((selector) => {
      const element = document.querySelector(selector);
      if (!element) {
        return { selector, exists: false };
      }
      const style = getComputedStyle(element);
      return {
        selector,
        exists: true,
        visible: isVisible(element),
        text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
        color: style.color,
        backgroundColor: effectiveBackground(element),
      };
    });
    const skipLink = document.querySelector(".skip-link");
    return {
      headings,
      focusables,
      contrastChecks,
      skipLink: skipLink
        ? {
            ...elementSummary(skipLink),
            targetExists: Boolean(document.querySelector(skipLink.getAttribute("href"))),
          }
        : { visible: false, targetExists: false },
    };
  });
}

function assertVisible(layout, viewportName) {
  for (const item of layout.visible) {
    assertLayout(item.exists, `${viewportName}: missing required section #${item.id}`, item);
    assertLayout(item.visible, `${viewportName}: required section #${item.id} is not visible`, item);
  }
}

function assertNoOverlaps(layout, viewportName) {
  const sections = layout.reviewSections;
  for (let leftIndex = 0; leftIndex < sections.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < sections.length; rightIndex += 1) {
      const overlap = rectOverlap(sections[leftIndex], sections[rightIndex]);
      assertLayout(
        overlap.x <= 2 || overlap.y <= 2,
        `${viewportName}: review sections overlap`,
        { a: sections[leftIndex], b: sections[rightIndex], overlap },
      );
    }
  }
}

function assertColumnGaps(layout, viewportName) {
  for (const column of layout.reviewColumns) {
    for (let index = 1; index < column.length; index += 1) {
      const previous = column[index - 1];
      const current = column[index];
      const gap = current.top - previous.bottom;
      assertLayout(
        gap >= 8 && gap <= 18,
        `${viewportName}: unexpected review-card vertical gap`,
        { previous, current, gap },
      );
    }
  }
}

function assertDesktopLayout(layout) {
  assertLayout(layout.live && layout.completeness, "desktop: missing core review cards", layout);
  const topDelta = Math.abs(layout.live.top - layout.completeness.top);
  assertLayout(topDelta <= 4, "desktop: Weather and Evidence Completeness should align", {
    live: layout.live,
    completeness: layout.completeness,
    topDelta,
  });
  assertLayout(
    layout.completeness.left > layout.live.left,
    "desktop: Evidence Completeness should sit to the right of Weather",
    { live: layout.live, completeness: layout.completeness },
  );
}

function assertStackedReviewLayout(layout, viewportName) {
  assertLayout(layout.live && layout.completeness, `${viewportName}: missing core review cards`, layout);
  assertLayout(
    layout.completeness.top > layout.live.top,
    `${viewportName}: Evidence Completeness should stack below Weather`,
    { live: layout.live, completeness: layout.completeness },
  );
}

function assertMobileLayout(layout) {
  for (const section of layout.reviewSections) {
    assertLayout(section.width > 280, "mobile: review card is unexpectedly narrow", section);
  }
}

function assertCardDensity(layout, viewport) {
  const thresholds =
    viewport.kind === "desktop"
      ? { live: 560, completeness: 250, trust: 310, warnings: 320 }
      : viewport.kind === "tablet"
        ? { live: 700, completeness: 300, trust: 360, warnings: 360 }
        : { live: 760, completeness: 340, trust: 420, warnings: 420 };
  for (const [key, threshold] of Object.entries(thresholds)) {
    const card = layout.densityCards[key];
    assertLayout(Boolean(card), `${viewport.name}: missing ${key} density card`, layout);
    assertLayout(card.height <= threshold, `${viewport.name}: ${key} card is too tall`, {
      card,
      threshold,
    });
  }
}

function assertResponsiveLayout(layout, viewport) {
  assertVisible(layout, viewport.name);
  assertNoOverlaps(layout, viewport.name);
  assertColumnGaps(layout, viewport.name);
  assertCardDensity(layout, viewport);
  if (viewport.kind === "desktop") {
    assertDesktopLayout(layout);
  } else {
    assertStackedReviewLayout(layout, viewport.name);
  }
  if (viewport.kind === "mobile") {
    assertMobileLayout(layout);
  }
}

function parseRgb(color) {
  const match = color.match(/^rgba?\((.*)\)$/);
  if (!match) {
    return null;
  }
  const parts = match[1].replace(/\//g, " ").replace(/,/g, " ").split(/\s+/).filter(Boolean);
  if (parts.length < 3) {
    return null;
  }
  const parseChannel = (value) => {
    if (value.endsWith("%")) {
      return (Number(value.slice(0, -1)) / 100) * 255;
    }
    return Number(value);
  };
  const channels = parts.slice(0, 3).map(parseChannel);
  if (channels.some((channel) => !Number.isFinite(channel))) {
    return null;
  }
  return channels.map((channel) => Math.max(0, Math.min(255, channel)));
}

function relativeLuminance(color) {
  return color
    .map((channel) => channel / 255)
    .map((channel) =>
      channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
    )
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
}

function contrastRatio(foreground, background) {
  const foregroundRgb = parseRgb(foreground);
  const backgroundRgb = parseRgb(background);
  assertLayout(Boolean(foregroundRgb && backgroundRgb), "accessibility: unable to parse colors", {
    foreground,
    background,
  });
  const foregroundLum = relativeLuminance(foregroundRgb);
  const backgroundLum = relativeLuminance(backgroundRgb);
  const lighter = Math.max(foregroundLum, backgroundLum);
  const darker = Math.min(foregroundLum, backgroundLum);
  return (lighter + 0.05) / (darker + 0.05);
}

function assertAccessibilityBasics(accessibility, viewportName) {
  assertLayout(accessibility.headings.length > 0, `${viewportName}: no headings found`);
  assertLayout(accessibility.headings[0].level === 1, `${viewportName}: first heading is not h1`, {
    headings: accessibility.headings.slice(0, 5),
  });
  for (let index = 1; index < accessibility.headings.length; index += 1) {
    const previous = accessibility.headings[index - 1];
    const current = accessibility.headings[index];
    assertLayout(
      current.level <= previous.level + 1,
      `${viewportName}: heading level skips`,
      { previous, current },
    );
    assertLayout(Boolean(current.text), `${viewportName}: empty heading`, current);
  }
  assertLayout(
    accessibility.skipLink.href === "#review-sections" && accessibility.skipLink.targetExists,
    `${viewportName}: skip link does not target review sections`,
    accessibility.skipLink,
  );
  assertLayout(
    accessibility.focusables.some((item) => String(item.className).includes("skip-link")),
    `${viewportName}: skip link is not keyboard focusable`,
    accessibility.focusables.slice(0, 8),
  );
  if (viewportName !== "mobile") {
    assertLayout(
      accessibility.focusables.some((item) => item.tag === "BUTTON" && /Print/.test(item.text)),
      `${viewportName}: print button is not keyboard focusable`,
      accessibility.focusables.slice(0, 8),
    );
  }
  assertLayout(
    accessibility.focusables.some((item) => String(item.className).includes("artifact-link")),
    `${viewportName}: artifact links are not keyboard focusable`,
    accessibility.focusables.slice(0, 12),
  );
  assertLayout(
    accessibility.focusables.some((item) => String(item.className).includes("review-section")),
    `${viewportName}: review cards are not keyboard focusable`,
    accessibility.focusables.slice(0, 12),
  );

  const renderedContrastChecks = accessibility.contrastChecks.filter(
    (check) => check.exists && check.visible,
  );
  assertLayout(
    renderedContrastChecks.length >= 6,
    `${viewportName}: too few rendered contrast check targets`,
    accessibility.contrastChecks,
  );
  for (const check of renderedContrastChecks) {
    const ratio = contrastRatio(check.color, check.backgroundColor);
    assertLayout(ratio >= 4.5, `${viewportName}: contrast ratio is too low`, {
      ...check,
      ratio,
    });
  }
}

async function activeElementInfo(page) {
  return page.evaluate(() => {
    const element = document.activeElement;
    if (!element) {
      return null;
    }
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      tag: element.tagName,
      id: element.id || "",
      className: element.className || "",
      text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
      href: element.getAttribute("href") || "",
      visible: rect.width > 0 && rect.height > 0,
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth) || 0,
      boxShadow: style.boxShadow,
    };
  });
}

function assertFocusIndicator(info, viewportName, label) {
  assertLayout(Boolean(info), `${viewportName}: no active element while checking ${label}`);
  const hasOutline = info.outlineStyle !== "none" && info.outlineWidth >= 2;
  const hasShadow = info.boxShadow && info.boxShadow !== "none";
  assertLayout(hasOutline || hasShadow, `${viewportName}: ${label} lacks visible focus style`, info);
}

async function tabToSelector(page, selector, maxTabs, viewportName) {
  for (let index = 0; index < maxTabs; index += 1) {
    await page.keyboard.press("Tab");
    const info = await activeElementInfo(page);
    const matches = await page.evaluate((targetSelector) => {
      return Boolean(document.activeElement && document.activeElement.matches(targetSelector));
    }, selector);
    if (matches) {
      return info;
    }
  }
  throw new Error(`${viewportName}: could not reach ${selector} through keyboard navigation`);
}

async function assertKeyboardAccessibility(page, viewportName) {
  await page.evaluate(() => {
    window.location.hash = "";
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });
  const skipInfo = await tabToSelector(page, ".skip-link", 5, viewportName);
  assertFocusIndicator(skipInfo, viewportName, "skip link");
  assertLayout(
    skipInfo.top >= 0 && skipInfo.bottom > skipInfo.top,
    `${viewportName}: focused skip link is not visible`,
    skipInfo,
  );
  const printInfo = await tabToSelector(page, ".print-button", 12, viewportName);
  assertFocusIndicator(printInfo, viewportName, "print button");

  await page.keyboard.down("Shift");
  await page.keyboard.press("Tab");
  await page.keyboard.up("Shift");
  const skipAgainInfo = await activeElementInfo(page);
  assertLayout(
    skipAgainInfo && String(skipAgainInfo.className).includes("skip-link"),
    `${viewportName}: shift-tab from print button did not return to skip link`,
    skipAgainInfo,
  );
  await page.keyboard.press("Enter");
  await page.waitForTimeout(80);
  const skipTargetVisible = await page.evaluate(() => {
    const target = document.getElementById("review-sections");
    if (!target) {
      return false;
    }
    const rect = target.getBoundingClientRect();
    return rect.top < window.innerHeight && rect.bottom > 0 && window.location.hash === "#review-sections";
  });
  assertLayout(skipTargetVisible, `${viewportName}: skip link did not move to review sections`);

  const reviewInfo = await tabToSelector(page, ".review-section", 120, viewportName);
  assertFocusIndicator(reviewInfo, viewportName, "review card");
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }

  const htmlPath = path.resolve(
    args.html || path.join(args.bundle, "operator_review_ui.html"),
  );
  assertLayout(fs.existsSync(htmlPath), `operator review UI not found: ${htmlPath}`);

  const outdir = path.resolve(args.outdir);
  fs.mkdirSync(outdir, { recursive: true });

  const { chromium } = loadPlaywright();
  const browser = await launchBrowser(chromium);
  const artifacts = [];
  const results = {};
  try {
    for (const viewport of RESPONSIVE_VIEWPORTS) {
      const page = await browser.newPage({
        viewport: { width: viewport.width, height: viewport.height },
      });
      await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
      await page.waitForTimeout(250);
      await page.locator("#review-sections").scrollIntoViewIfNeeded();
      const screenshotPath = path.join(outdir, `operator-review-${viewport.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: false });
      artifacts.push(screenshotPath);
      const layout = await collectLayout(page);
      results[viewport.name] = layout;
      assertResponsiveLayout(layout, viewport);
      const accessibility = await collectAccessibility(page);
      results[`${viewport.name}Accessibility`] = accessibility;
      assertAccessibilityBasics(accessibility, viewport.name);
      if (viewport.name === "desktop-1366") {
        await assertKeyboardAccessibility(page, viewport.name);
      }
      await page.close();
    }

    const printPage = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await printPage.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    await printPage.emulateMedia({ media: "print" });
    await printPage.waitForTimeout(250);
    const printPng = path.join(outdir, "operator-review-print-preview.png");
    await printPage.screenshot({ path: printPng, fullPage: false });
    artifacts.push(printPng);
    const pdfPath = path.join(outdir, "operator-review-print.pdf");
    await printPage.pdf({
      path: pdfPath,
      format: "Letter",
      printBackground: true,
      margin: { top: "0.35in", right: "0.35in", bottom: "0.35in", left: "0.35in" },
    });
    artifacts.push(pdfPath);
    results.print = await collectLayout(printPage);
    assertVisible(results.print, "print");
    assertLayout(
      results.print.reviewDisplay === "block",
      "print: review sections should use block flow",
      results.print,
    );
    assertLayout(
      String(results.print.freshnessColumns || "").split(" ").length >= 2,
      "print: artifact freshness list should use compact columns",
      results.print,
    );
    assertLayout(
      fs.statSync(pdfPath).size > 10000,
      "print: generated PDF is unexpectedly small",
      { pdfPath, size: fs.statSync(pdfPath).size },
    );
    await printPage.close();
  } finally {
    await browser.close();
  }

  const summary = {
    ok: true,
    htmlPath,
    outdir,
    artifacts,
    checkedViewports: [...RESPONSIVE_VIEWPORTS.map((viewport) => viewport.name), "print"],
    accessibilityChecks: ["heading order", "focus states", "contrast", "skip link", "keyboard"],
  };
  if (args.json) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.log("Operator review UI layout check passed.");
    for (const artifact of artifacts) {
      console.log(`- ${artifact}`);
    }
  }

  if (!args.keepArtifacts) {
    for (const artifact of artifacts) {
      try {
        fs.unlinkSync(artifact);
      } catch (_err) {
        // Ignore cleanup failures; the check has already passed.
      }
    }
    try {
      fs.rmdirSync(outdir);
    } catch (_err) {
      // Keep non-empty output directories.
    }
  }
}

run().catch((error) => {
  console.error(error.message);
  if (error.details) {
    console.error(JSON.stringify(error.details, null, 2));
  }
  process.exit(1);
});
