# BVLOS What-If Planning

Mission: BVLOS Modify No-Go Fixture

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| HIGH | no | 260.0 | 11.0 | -41.0 | 3.6 |

## Scenario Comparisons

| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | Changed time -125.0 s, energy -2.4 Wh, battery reserve +2.4 Wh. | HIGH | no | 135.0 | -125.0 | 8.7 | -38.7 | Battery reserve margin |
| Lower speed | Changed time -45.0 s, energy +1.6 Wh, battery reserve -1.6 Wh. | HIGH | no | 215.0 | -45.0 | 12.6 | -42.6 | Battery reserve margin |
| Alternate launch point | Changed time -70.0 s, energy +0.892 Wh, battery reserve -0.892 Wh. | HIGH | no | 190.0 | -70.0 | 11.9 | -41.9 | Battery reserve margin |
| Stronger wind case | Changed time -10.0 s, energy +0.295 Wh, battery reserve -0.295 Wh. | HIGH | no | 250.0 | -10.0 | 11.3 | -41.3 | Battery reserve margin |
| Larger battery reserve requirement | Changed time -90.0 s, energy +4.3 Wh, battery reserve +20.7 Wh. | HIGH | no | 170.0 | -90.0 | 15.3 | -20.3 | Battery reserve margin |
| Relaunch / battery swap | Changed time -40.0 s, energy +1.4 Wh, battery reserve +4.2 Wh. | HIGH | no | 220.0 | -40.0 | 12.5 | -36.9 | Battery reserve margin |

## Before / After Improvements

These scenarios improve at least one feasibility or audit margin versus the baseline plan.

| Scenario | Improved metric | Baseline | After | Delta |
| --- | --- | ---: | ---: | ---: |
| Fewer waypoints | Battery reserve margin | -41.0 Wh | -38.7 Wh | 2.4 Wh |
| Fewer waypoints | Geofence clearance margin | 273.1 m | 278.2 m | 5.0 m |
| Lower speed | Turn / bank margin | 0.252 rad/s | 0.254 rad/s | 0.00228 rad/s |
| Alternate launch point | Geofence clearance margin | 273.1 m | 278.0 m | 4.9 m |
| Stronger wind case | Geofence clearance margin | 273.1 m | 282.9 m | 9.7 m |
| Larger battery reserve requirement | Battery reserve margin | -41.0 Wh | -20.3 Wh | 20.7 Wh |
| Relaunch / battery swap | Battery reserve margin | -41.0 Wh | -36.9 Wh | 4.2 Wh |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
