# BVLOS What-If Planning

Mission: BVLOS Powerline Inspection Demo

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 220.0 | 11.9 | 138.1 | 3.1 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -105.0 s, energy -1.9 Wh, battery reserve +1.9 Wh. | LOW | yes | 115.0 | -105.0 | 10.0 | 140.0 | Wind / weather margin |
| Lower speed | Changed time -10.0 s, energy +0.424 Wh, battery reserve -0.424 Wh. | LOW | yes | 210.0 | -10.0 | 12.3 | 137.7 | Wind / weather margin |
| Alternate launch point | Changed energy -1.7 Wh, battery reserve +1.7 Wh. | LOW | yes | 220.0 | 0.0 | 10.2 | 139.8 | Wind / weather margin |
| Stronger wind case | Changed time -70.0 s, energy +5.0 Wh, battery reserve -5.0 Wh. | LOW | yes | 150.0 | -70.0 | 16.9 | 133.1 | Wind / weather margin |
| Larger battery reserve requirement | Changed time -80.0 s, energy +6.6 Wh, battery reserve -111.6 Wh. | MEDIUM | yes | 140.0 | -80.0 | 18.5 | 26.5 | Battery reserve margin |
| Relaunch / battery swap | Changed time -20.0 s, energy +1.1 Wh, battery reserve +5.3 Wh. | LOW | yes | 200.0 | -20.0 | 13.0 | 143.4 | Wind / weather margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | 138.1 Wh | 140.0 Wh | 1.9 Wh |
| Fewer waypoints | Geofence clearance margin | 266.0 m | 274.8 m | 8.8 m |
| Lower speed | Geofence clearance margin | 266.0 m | 284.4 m | 18.4 m |
| Lower speed | Turn / bank margin | 0.236 rad/s | 0.254 rad/s | 0.0174 rad/s |
| Alternate launch point | Battery reserve margin | 138.1 Wh | 139.8 Wh | 1.7 Wh |
| Alternate launch point | Geofence clearance margin | 266.0 m | 288.9 m | 22.9 m |
| Alternate launch point | Turn / bank margin | 0.236 rad/s | 0.251 rad/s | 0.0144 rad/s |
| Larger battery reserve requirement | Geofence clearance margin | 266.0 m | 270.8 m | 4.8 m |
| Relaunch / battery swap | Battery reserve margin | 138.1 Wh | 143.4 Wh | 5.3 Wh |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
