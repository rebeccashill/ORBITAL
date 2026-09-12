# ORBITAL Market Proof

This document states the market thesis behind ORBITAL v1.0.8. It is written as
a set of operator-focused assumptions to test, not as a claim of completed
customer validation.

## Problem Statement

Inspection operators are being asked to cover longer corridors, more assets, and
more weather-sensitive field windows with drone teams. The hard question is not
only "Where should the aircraft fly?" It is:

> Can we safely and defensibly fly this inspection mission before sending a crew
> into the field?

For BVLOS and extended-corridor inspections, that answer depends on overlapping
constraints: battery reserve, route completion, wind and weather margin,
geofence clearance, turn feasibility, crew roles, airspace requirements,
customer site permissions, regulatory evidence, and emergency procedures.

Generic planning tools often handle one slice of that workflow. Operators still
need a reviewable feasibility case that explains which constraints bind, what
alternatives improve the plan, what evidence is missing, and what the
pilot-in-command must confirm before dispatch.

## Buyer And User Assumptions

Economic buyers are likely to be inspection, asset integrity, field operations,
or UAS program leaders who own crew productivity, asset uptime, safety process,
or inspection cost.

Technical evaluators are likely to be chief remote pilots, UAS operations
managers, safety and compliance leads, GIS or remote sensing analysts, and
flight operations engineers.

Daily users are likely to be mission planners, remote pilots in command,
operations coordinators, visual observer coordinators, and analysts preparing
mission evidence packages.

Purchasing or adoption triggers may include scaling BVLOS inspection programs,
missed or scrubbed field deployments, pressure to standardize preflight review,
internal audit requirements, customer requests for mission evidence, or
regulatory readiness work for repeatable corridor operations.

Success should be measured by operational outcomes: faster feasibility review,
clearer go/no-go rationale, fewer avoidable field dispatches, better evidence
packages, more consistent crew briefings, and more transparent assumptions for
approvers.

## Target Customer Profiles

| Segment | Inspection job | Likely buyer | Likely users | Why ORBITAL fits |
| --- | --- | --- | --- | --- |
| Utility | Powerline, substation, storm-damage, and vegetation-adjacent corridor inspection | Director of utility inspection, UAS program manager, grid operations leader | Mission planner, remote pilot in command, visual observer coordinator, asset engineer | Utility missions need corridor coverage, weather margin, geofence review, crew readiness, and evidence that the mission decision was defensible. |
| Pipeline | Right-of-way, leak-survey support, construction, encroachment, and post-event inspection | Pipeline integrity manager, field operations leader, UAS program owner | Remote sensing analyst, mission planner, pilot, operations coordinator | Pipeline routes create long linear missions where battery reserve, launch location, route completion, and customer/site constraints determine whether a sortie is practical. |
| Rail | Track, bridge, yard, signal, and post-incident infrastructure inspection | Rail infrastructure manager, safety operations leader, drone program manager | Corridor planner, pilot, safety reviewer, GIS analyst | Rail inspections need conservative geofence and route-completion evidence because missions often run near public corridors, industrial sites, and complex operating boundaries. |
| Renewable energy | Wind farm, solar farm, battery site, and transmission tie-in inspection | Renewable operations manager, asset performance leader, inspection services manager | Site planner, drone pilot, O&M analyst, contractor coordinator | Renewable operators need repeatable inspection packages across many sites, with weather, battery, and customer evidence tracked consistently. |
| Emergency infrastructure | Storm, wildfire, flood, outage, and damage-assessment inspection | Emergency response operations leader, public works or utility incident lead | Response planner, pilot, field coordinator, command staff analyst | Emergency missions need fast feasibility review, explicit assumptions, contingency planning, and evidence that can be briefed under time pressure. |

## Top Alternatives

| Alternative | What it usually solves | Gap for inspection operators | Why ORBITAL is different |
| --- | --- | --- | --- |
| Generic route planners | Drawing or importing waypoints and visualizing a route | They may not explain whether the route is defensible under battery, wind, geofence, route-completion, and turn constraints. | ORBITAL makes the constraint audit the primary artifact and reports pass / warning / fail margins with operator-facing actions. |
| Fleet management tools | Aircraft, pilot, battery, job, maintenance, and log administration | They are often systems of record rather than feasibility engines for a specific proposed mission. | ORBITAL focuses on preflight feasibility and evidence before a crew is committed. |
| Autopilot or ground-control software | Executing or uploading flight plans to aircraft | Execution tooling does not by itself create an operator-ready argument for why the mission should proceed. | ORBITAL produces planning-only exports and keeps final execution authority outside the system. |
| LAANC and airspace tools | Airspace authorization workflows or airspace data lookup | Authorization status is only one part of the mission decision, and authorization does not prove the route is operationally sound. | ORBITAL records regulatory readiness and evidence fields while explicitly avoiding legal approval claims. |
| GIS viewers | Displaying routes, boundaries, assets, and spatial context | Spatial visibility does not automatically produce constraint margins, limiting risks, what-if alternatives, or audit bundles. | ORBITAL turns route and geofence data into feasibility evidence and review artifacts. |
| Spreadsheets and manual checklists | Flexible ad hoc planning and operator review | Manual workflows can be inconsistent, hard to reproduce, and disconnected from simulation outputs. | ORBITAL generates structured JSON, Markdown, CSV, KML, manifests, and checksums from the same modeled scenario. |
| Consulting or one-off engineering analysis | Bespoke feasibility studies for high-value operations | Custom analysis can be slow, expensive, and hard to repeat across routine inspection missions. | ORBITAL aims to make repeatable constraint-audit and evidence workflows available inside day-to-day planning. |

## Market Proof To Collect Next

- Interview inspection operators about recent missions that were delayed,
  scrubbed, reworked, or hard to justify internally.
- Ask buyers which evidence artifacts they already need for customer,
  regulatory, safety, or internal review.
- Time the current preflight feasibility workflow and compare it with the
  ORBITAL evidence workflow.
- Test whether the constraint-audit report changes planning conversations more
  than a map-first route preview.
- Validate which vertical has the sharpest initial wedge: utility, pipeline,
  rail, renewable energy, or emergency infrastructure.
- Confirm the minimum integrations needed for adoption, such as GIS files,
  route exports, weather data, fleet metadata, or approval records.
