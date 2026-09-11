# BVLOS What-If Planning

Mission: BVLOS Powerline Inspection Demo

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 140.0 | 17.9 | 132.1 | 3.1 |

## Scenario Comparisons

| Scenario | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | LOW | yes | 95.0 | -45.0 | 11.8 | 138.2 | Wind / weather margin |
| Lower speed | LOW | yes | 210.0 | 70.0 | 12.3 | 137.7 | Wind / weather margin |
| Alternate launch point | LOW | yes | 180.0 | 40.0 | 23.8 | 126.2 | Wind / weather margin |
| Stronger wind case | LOW | yes | 140.0 | 0.0 | 17.9 | 132.1 | Wind / weather margin |
| Larger battery reserve requirement | MEDIUM | yes | 140.0 | 0.0 | 18.0 | 27.0 | Battery reserve margin |
| Relaunch / battery swap | LOW | yes | 150.0 | 10.0 | 16.8 | 141.6 | Wind / weather margin |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
