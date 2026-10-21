# Data card: dataset_v1

- Designs: 151. Requests: 348. Questions: 875.
- Requests per kind: {'basic': 151, 'performance': 110, 'reason': 25, 'pair': 62}.
- Questions per key: {'compiles': 151, 'synthesizes': 151, 'slack': 110, 'reach': 110, 'area': 110, 'power': 98, 'reason': 25, 'smaller_area': 58, 'lower_power': 50, 'higher_reach': 12}.
- Pairs: 31 (each in two orders).
- Skipped: {'no power (power_failed)': 12, 'no slack or area': 4, 'mutant: DC class is not the intended class': 4, 'trap side does not synthesize': 2, 'noncompile: DC class is not the intended class': 2, 'pair: no value differs by 10%': 11, 'pair: different testbench': 3}.

| Group | Designs | basic | reason | performance | pair |
|---|---|---|---|---|---|
| metrex | 40 | 40 | 1 | 37 | 0 |
| mutant | 16 | 16 | 16 | 0 | 0 |
| natural | 20 | 20 | 1 | 18 | 0 |
| noncompile | 8 | 8 | 0 | 0 | 0 |
| reference | 15 | 15 | 0 | 14 | 0 |
| revold | 32 | 32 | 1 | 31 | 62 |
| revolution | 10 | 10 | 0 | 10 | 0 |
| trap | 10 | 10 | 6 | 0 | 0 |

Correct answers per question key (all splits):

- `area`: {'1': 37, '2': 34, '3': 24, '4': 10, '5': 5}
- `compiles`: {'False': 12, 'True': 139}
- `higher_reach`: {'A': 6, 'B': 6}
- `lower_power`: {'A': 25, 'B': 25}
- `power`: {'1': 25, '2': 45, '3': 20, '4': 7, '5': 1}
- `reach`: {'1': 16, '2': 17, '3': 26, '4': 51}
- `reason`: {'async_reset': 1, 'event_list': 1, 'illegal_code': 4, 'instance_mismatch': 2, 'mixed_assignments': 2, 'multiple_drivers': 3, 'simulation_statement': 6, 'timing_control': 4, 'unbounded_loop': 1, 'unsupported_construct': 1}
- `slack`: {'2': 6, '3': 10, '4': 17, '5': 77}
- `smaller_area`: {'A': 29, 'B': 29}
- `synthesizes`: {'False': 33, 'True': 118}

- Split (requests): {'test': 281, 'dev': 67}.
- Estimated tokens per request: median 1510, maximum 7966; above 8,000: 0.
