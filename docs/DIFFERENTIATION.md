# ORBITAL Differentiation

## Category

ORBITAL is constraint-aware BVLOS inspection feasibility and audit evidence
software.

It is not a generic route planner, fleet dashboard, autopilot, LAANC provider,
or GIS viewer. ORBITAL sits before dispatch, when an operator needs to answer a
hard operational question:

> Can we safely and defensibly fly this mission?

That question is broader than "Can we draw a route?" ORBITAL evaluates whether a
candidate inspection mission is feasible under modeled constraints, identifies
the constraints that matter most, compares practical alternatives, and packages
evidence that an operator can review before committing a crew.

## What Makes ORBITAL Different

Most drone planning tools are organized around maps, routes, assets, airspace
lookups, fleet records, or execution. ORBITAL is organized around mission
defensibility: battery reserve, weather margins, geofence clearance, route
completion, turn feasibility, robustness, regulatory documentation, and
operator evidence.

ORBITAL's core workflow is:

1. Model the mission, vehicle, route, weather, geofence, and operating context.
2. Optimize a candidate plan against hard and soft constraints.
3. Audit the plan with transparent pass / warning / fail constraint groups,
   operator-facing explanations, and limiting constraints.
4. Generate what-if alternatives that show operational tradeoffs.
5. Bundle review artifacts, regulatory readiness, checklists, and manifests for
   operator decision support.

The result is not an approval to fly. It is a structured feasibility case that
helps the pilot-in-command and operator decide what must be changed, confirmed,
or escalated before the mission proceeds.

For the market thesis behind this positioning, including buyer/user
assumptions, target inspection customer profiles, and top alternatives, see
[Market Proof](MARKET_PROOF.md).

## Comparison

| Capability | Generic drone planning software | ORBITAL |
| --- | --- | --- |
| Primary question | Where should the drone fly? | Can we safely and defensibly fly this mission? |
| Planning center | Map route, waypoint list, or mission upload | Constraint-aware feasibility, audit evidence, and tradeoff analysis |
| Route planning | Draws or imports paths | Optimizes candidate plans against battery, weather, geofence, turn, and completion constraints |
| Constraint visibility | Often hidden, implicit, or limited to warnings | Produces explicit hard/soft constraint margins and top limiting risk drivers |
| What-if workflow | Usually manual duplicate-and-edit planning | Generates structured alternatives such as fewer waypoints, lower speed, alternate launch, stronger wind, and larger reserves |
| Evidence output | Screenshots, logs, or basic exports | JSON, Markdown, CSV, KML, regulatory readiness, checklists, and operator evidence bundles |
| Regulatory posture | May connect to airspace authorization or present airspace data | Documents regulatory assumptions and evidence fields while explicitly avoiding legal approval claims |
| Operator role | Often focused on execution workflow | Keeps final go/no-go, approvals, crew readiness, and legal responsibility with the operator |
| Robustness | Limited sensitivity analysis | Monte Carlo robustness summaries and constraint stress visibility |
| Best fit | Routine route setup or fleet operations | BVLOS inspection planning where feasibility, defensibility, and audit trail matter |

## Adjacent Tool Boundaries

### Route Planners

Route planners help create waypoints and mission paths. ORBITAL can use routes,
but its differentiator is deciding whether the route is feasible under mission
constraints and what evidence supports that conclusion.

### Fleet Tools

Fleet tools track aircraft, pilots, batteries, maintenance, jobs, and logs.
ORBITAL can document fleet and mission metadata, but it is focused on preflight
constraint evidence rather than system-of-record fleet administration.

### Autopilots

Autopilots execute flight commands. ORBITAL does not control an aircraft.
Downstream exports are planning artifacts only and require operator review
before any operational use.

### LAANC Providers

LAANC providers request or manage airspace authorization. ORBITAL does not issue
LAANC, waivers, authorizations, or legal clearance. It records documentation-only
regulatory metadata so operators can see what must be confirmed outside ORBITAL.

### GIS Viewers

GIS viewers display spatial data. ORBITAL can ingest routes and geofences, but
it turns those spatial inputs into feasibility constraints, margins, audit
evidence, and operator-facing reports.

## Differentiation Pillars

- Constraint audit: ORBITAL makes feasibility explainable through named
  constraints, pass / warning / fail status, margins, penalties, top risk
  drivers, plain-English operator impact, and recommended actions.
- What-if planning: ORBITAL shows practical alternatives when a mission is tight,
  risky, or infeasible, including before/after comparisons when an alternative
  improves feasibility evidence.
- Evidence workflow: ORBITAL exports review-ready artifacts, manifests, memos,
  regulatory readiness reports, checklists, bundle summaries, artifact indexes,
  completeness scores, review status, and checksum manifests.
- Legal honesty: ORBITAL is decision support. It does not imply flight approval,
  legal approval, airspace authorization, autopilot control, or operational
  clearance.
- BVLOS inspection focus: ORBITAL is shaped around inspection operators who need
  to defend a mission decision before sending crews into the field.

## HBS-Ready Positioning

ORBITAL is a preflight feasibility and evidence layer for BVLOS inspection
operators. While generic drone tools help teams draw routes, manage fleets,
view maps, or execute flights, ORBITAL answers the higher-stakes planning
question: "Can we safely and defensibly fly this mission?" It combines
constraint-aware optimization, transparent audit reports, what-if alternatives,
and documentation-only regulatory readiness artifacts so operators can identify
binding risks, compare changes, and prepare a reviewable mission package before
field deployment.
