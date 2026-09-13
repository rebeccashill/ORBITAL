# BVLOS What-If Planning

Mission: BVLOS Powerline Inspection Demo

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 140.0 | 17.9 | 132.1 | 3.1 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -45.0 s, energy -6.2 Wh, battery reserve +6.2 Wh. | LOW | yes | 95.0 | -45.0 | 11.8 | 138.2 | Wind / weather margin |
| Lower speed | Changed time +70.0 s, energy -5.6 Wh, battery reserve +5.6 Wh. | LOW | yes | 210.0 | 70.0 | 12.3 | 137.7 | Wind / weather margin |
| Alternate launch point | Changed time +40.0 s, energy +5.9 Wh, battery reserve -5.9 Wh. | LOW | yes | 180.0 | 40.0 | 23.8 | 126.2 | Wind / weather margin |
| Stronger wind case | Changed energy +0.00239 Wh, battery reserve -0.00239 Wh. | LOW | yes | 140.0 | 0.0 | 17.9 | 132.1 | Wind / weather margin |
| Larger battery reserve requirement | Changed energy +0.0462 Wh, battery reserve -105.0 Wh. | MEDIUM | yes | 140.0 | 0.0 | 18.0 | 27.0 | Battery reserve margin |
| Relaunch / battery swap | Changed time +10.0 s, energy -1.1 Wh, battery reserve +9.5 Wh. | LOW | yes | 150.0 | 10.0 | 16.8 | 141.6 | Wind / weather margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | 132.1 Wh | 138.2 Wh | 6.2 Wh |
| Fewer waypoints | Geofence clearance margin | 276.7 m | 278.4 m | 1.7 m |
| Lower speed | Battery reserve margin | 132.1 Wh | 137.7 Wh | 5.6 Wh |
| Lower speed | Geofence clearance margin | 276.7 m | 284.4 m | 7.7 m |
| Lower speed | Turn / bank margin | 0.139 rad/s | 0.254 rad/s | 0.115 rad/s |
| Alternate launch point | Geofence clearance margin | 276.7 m | 277.3 m | 0.576 m |
| Relaunch / battery swap | Battery reserve margin | 132.1 Wh | 141.6 Wh | 9.5 Wh |
| Relaunch / battery swap | Turn / bank margin | 0.139 rad/s | 0.144 rad/s | 0.00463 rad/s |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
