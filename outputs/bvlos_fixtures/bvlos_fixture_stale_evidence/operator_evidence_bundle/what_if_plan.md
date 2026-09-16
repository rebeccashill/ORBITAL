# BVLOS What-If Planning

Mission: BVLOS Stale Evidence Fixture

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 185.0 | 13.8 | 136.2 | 3.1 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -40.0 s, energy -5.6 Wh, battery reserve +5.6 Wh. | LOW | yes | 145.0 | -40.0 | 8.2 | 141.8 | Wind / weather margin |
| Lower speed | Changed time +25.0 s, energy -1.5 Wh, battery reserve +1.5 Wh. | LOW | yes | 210.0 | 25.0 | 12.3 | 137.7 | Wind / weather margin |
| Alternate launch point | Changed time -30.0 s, energy -0.206 Wh, battery reserve +0.206 Wh. | LOW | yes | 155.0 | -30.0 | 13.6 | 136.4 | Wind / weather margin |
| Stronger wind case | Changed energy -0.189 Wh, battery reserve +0.189 Wh. | LOW | yes | 185.0 | 0.0 | 13.6 | 136.4 | Wind / weather margin |
| Larger battery reserve requirement | Changed time -25.0 s, energy +2.1 Wh, battery reserve -107.1 Wh. | MEDIUM | yes | 160.0 | -25.0 | 15.9 | 29.1 | Battery reserve margin |
| Relaunch / battery swap | Changed time -30.0 s, energy +2.9 Wh, battery reserve +5.1 Wh. | LOW | yes | 155.0 | -30.0 | 16.7 | 141.3 | Wind / weather margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | 136.2 Wh | 141.8 Wh | 5.6 Wh |
| Fewer waypoints | Geofence clearance margin | 272.7 m | 277.8 m | 5.1 m |
| Fewer waypoints | Turn / bank margin | 0.201 rad/s | 0.233 rad/s | 0.0318 rad/s |
| Lower speed | Battery reserve margin | 136.2 Wh | 137.7 Wh | 1.5 Wh |
| Lower speed | Geofence clearance margin | 272.7 m | 284.4 m | 11.7 m |
| Lower speed | Turn / bank margin | 0.201 rad/s | 0.254 rad/s | 0.0526 rad/s |
| Alternate launch point | Battery reserve margin | 136.2 Wh | 136.4 Wh | 0.206 Wh |
| Alternate launch point | Geofence clearance margin | 272.7 m | 278.0 m | 5.3 m |
| Stronger wind case | Battery reserve margin | 136.2 Wh | 136.4 Wh | 0.189 Wh |
| Stronger wind case | Geofence clearance margin | 272.7 m | 277.1 m | 4.4 m |
| Stronger wind case | Turn / bank margin | 0.201 rad/s | 0.204 rad/s | 0.00226 rad/s |
| Relaunch / battery swap | Battery reserve margin | 136.2 Wh | 141.3 Wh | 5.1 Wh |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
