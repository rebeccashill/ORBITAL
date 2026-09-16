# BVLOS What-If Planning

Mission: BVLOS Missing Artifact Fixture

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 235.0 | 11.7 | 138.3 | 3.6 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -135.0 s, energy -0.173 Wh, battery reserve +0.173 Wh. | LOW | yes | 100.0 | -135.0 | 11.5 | 138.5 | Wind / weather margin |
| Lower speed | Changed time -20.0 s, energy +0.924 Wh, battery reserve -0.924 Wh. | LOW | yes | 215.0 | -20.0 | 12.6 | 137.4 | Wind / weather margin |
| Alternate launch point | Changed time -60.0 s, energy +1.0 Wh, battery reserve -1.0 Wh. | LOW | yes | 175.0 | -60.0 | 12.7 | 137.3 | Wind / weather margin |
| Stronger wind case | Changed time -75.0 s, energy +4.4 Wh, battery reserve -4.4 Wh. | LOW | yes | 160.0 | -75.0 | 16.1 | 133.9 | Wind / weather margin |
| Larger battery reserve requirement | Changed time -80.0 s, energy +4.9 Wh, battery reserve -109.9 Wh. | MEDIUM | yes | 155.0 | -80.0 | 16.6 | 28.4 | Battery reserve margin |
| Relaunch / battery swap | Changed time -75.0 s, energy +4.7 Wh, battery reserve +3.0 Wh. | LOW | yes | 160.0 | -75.0 | 16.3 | 141.3 | Wind / weather margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | 138.3 Wh | 138.5 Wh | 0.173 Wh |
| Lower speed | Turn / bank margin | 0.244 rad/s | 0.254 rad/s | 0.00965 rad/s |
| Relaunch / battery swap | Battery reserve margin | 138.3 Wh | 141.3 Wh | 3.0 Wh |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
