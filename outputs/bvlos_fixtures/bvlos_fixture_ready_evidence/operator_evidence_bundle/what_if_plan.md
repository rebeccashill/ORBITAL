# BVLOS What-If Planning

Mission: BVLOS Ready Evidence Fixture

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 165.0 | 15.6 | 134.4 | 3.6 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -45.0 s, energy -6.0 Wh, battery reserve +6.0 Wh. | LOW | yes | 120.0 | -45.0 | 9.6 | 140.4 | Wind / weather margin |
| Lower speed | Changed time +50.0 s, energy -3.0 Wh, battery reserve +3.0 Wh. | LOW | yes | 215.0 | 50.0 | 12.6 | 137.4 | Wind / weather margin |
| Alternate launch point | Changed time -10.0 s, energy -1.2 Wh, battery reserve +1.2 Wh. | LOW | yes | 155.0 | -10.0 | 14.4 | 135.6 | Wind / weather margin |
| Stronger wind case | Changed time -10.0 s, energy +1.2 Wh, battery reserve -1.2 Wh. | LOW | yes | 155.0 | -10.0 | 16.8 | 133.2 | Wind / weather margin |
| Larger battery reserve requirement | Changed time +30.0 s, energy -2.2 Wh, battery reserve -102.8 Wh. | MEDIUM | yes | 195.0 | 30.0 | 13.4 | 31.6 | Battery reserve margin |
| Relaunch / battery swap | Changed time +5.0 s, energy -0.456 Wh, battery reserve +8.0 Wh. | LOW | yes | 170.0 | 5.0 | 15.2 | 142.4 | Wind / weather margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | 134.4 Wh | 140.4 Wh | 6.0 Wh |
| Fewer waypoints | Geofence clearance margin | 254.1 m | 276.5 m | 22.4 m |
| Fewer waypoints | Turn / bank margin | 0.166 rad/s | 0.19 rad/s | 0.0242 rad/s |
| Lower speed | Battery reserve margin | 134.4 Wh | 137.4 Wh | 3.0 Wh |
| Lower speed | Geofence clearance margin | 254.1 m | 266.7 m | 12.6 m |
| Lower speed | Turn / bank margin | 0.166 rad/s | 0.254 rad/s | 0.0884 rad/s |
| Alternate launch point | Battery reserve margin | 134.4 Wh | 135.6 Wh | 1.2 Wh |
| Alternate launch point | Geofence clearance margin | 254.1 m | 267.7 m | 13.6 m |
| Stronger wind case | Geofence clearance margin | 254.1 m | 269.0 m | 14.9 m |
| Larger battery reserve requirement | Geofence clearance margin | 254.1 m | 278.1 m | 24.0 m |
| Larger battery reserve requirement | Turn / bank margin | 0.166 rad/s | 0.215 rad/s | 0.0496 rad/s |
| Relaunch / battery swap | Battery reserve margin | 134.4 Wh | 142.4 Wh | 8.0 Wh |
| Relaunch / battery swap | Turn / bank margin | 0.166 rad/s | 0.172 rad/s | 0.00657 rad/s |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
