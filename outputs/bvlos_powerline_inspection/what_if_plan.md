# BVLOS What-If Planning

Mission: BVLOS Powerline Inspection Demo

## Baseline

| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |
| --- | --- | ---: | ---: | ---: | ---: |
| LOW | yes | 140.0 | 18.1 | 131.9 | 3.5 |

## Scenario Comparisons

| Scenario | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | Battery Margin | Top Limiter |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Fewer waypoints | LOW | yes | 95.0 | -45.0 | 11.9 | 138.1 | Wind / weather margin |
| Lower speed | LOW | yes | 210.0 | 70.0 | 12.3 | 137.7 | Wind / weather margin |
| Alternate launch point | LOW | yes | 185.0 | 45.0 | 22.5 | 127.5 | Wind / weather margin |
| Stronger wind case | MEDIUM | yes | 130.0 | -10.0 | 16.6 | 133.4 | Wind / weather margin |
| Larger battery reserve requirement | MEDIUM | yes | 140.0 | 0.0 | 18.2 | 26.8 | Battery reserve margin |
| Relaunch / battery swap | LOW | yes | 150.0 | 10.0 | 17.1 | 141.4 | Wind / weather margin |

## Notes

- Fewer waypoints: Drop the final inspection points to compare a shorter sortie.
- Lower speed: Force a lower cruise speed to compare endurance and turn margin.
- Alternate launch point: Move launch closer to the first tower / inspection corridor.
- Stronger wind case: Increase modeled wind components by 50 percent.
- Larger battery reserve requirement: Increase the required final battery reserve.
- Relaunch / battery swap: Split the route into two sorties with a fresh battery for the second leg.
