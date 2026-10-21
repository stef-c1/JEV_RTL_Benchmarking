# mac_int8 on NanGate 45nm and NanGate 15nm

Both runs use the same RTL, the same testbenches, and the same `config.sh`.
Only `TECH` differs. Every step passed in both runs, at both frequencies.

Reproduce a row with:

```bash
TECH=nangate45 CLOCK_FREQ_MHZ=200 RESULTS_DIR=$PWD/results_200_nangate45 ./run_all.sh
TECH=nangate15 CLOCK_FREQ_MHZ=200 RESULTS_DIR=$PWD/results_200_nangate15 ./run_all.sh
```

## At 200 MHz, where neither library is timing limited

| Quantity | 45nm | 15nm | 45nm / 15nm |
| --- | --- | --- | --- |
| Cell area | 596.638 um2 | 159.547 um2 | 3.74x |
| Leaf cells | 328 | 360 | 0.91x |
| Worst slack | 1.58 ns of 5.00 ns | 4138 ps of 5000 ps | |
| Total power | 0.1537 mW | 0.04487 mW | 3.43x |
| Cell internal | 0.08018 mW | 0.02350 mW | 3.41x |
| Net switching | 0.06074 mW | 0.01580 mW | 3.84x |
| Cell leakage | 0.01277 mW | 0.005568 mW | 2.29x |

## At 500 MHz, where the 45nm run is timing limited

| Quantity | 45nm | 15nm | 45nm / 15nm |
| --- | --- | --- | --- |
| Cell area | 697.452 um2 | 159.547 um2 | 4.37x |
| Leaf cells | 452 | 360 | 0.73x |
| Worst slack | 0.02 ns of 2.00 ns | 1438 ps of 2000 ps | |
| Total power | 0.3954 mW | 0.1038 mW | 3.81x |
| Cell leakage | 0.0149 mW | 0.005568 mW | 2.68x |

The 45nm area grows from 597 to 697 um2 between the two frequencies, because
Design Compiler adds drive strength to meet 500 MHz. The 15nm area does not
change, because 500 MHz never constrains that library.

## Maximum frequency

Found by synthesis alone, one run per point.

| Library | Highest frequency met | Lowest frequency missed |
| --- | --- | --- |
| 45nm | 900 MHz, slack 0.0000 ns | 950 MHz, slack -0.0281 ns |
| 15nm | 6000 MHz, slack 0.21 ps | 7000 MHz, slack -15.04 ps |

The 15nm library reaches about 6.7 times the frequency of the 45nm library.

## Checks that the flow behaves correctly

Dynamic power must scale with the clock frequency, and leakage must not.
Between 200 MHz and 500 MHz, a frequency ratio of 2.500:

- 15nm dynamic power ratio 2.500, and the leakage is 0.005568 mW at both
  frequencies. The netlist is the same, so this is the exact result.
- 45nm dynamic power ratio 2.700, above the frequency ratio because the
  netlist grew to meet 500 MHz.

Power density rises as the node shrinks, and leakage density rises faster.
At 200 MHz:

| Quantity | 45nm | 15nm | 15nm / 45nm |
| --- | --- | --- | --- |
| Total power density | 2.576e-04 mW/um2 | 2.812e-04 mW/um2 | 1.09x |
| Leakage density | 2.140e-05 mW/um2 | 3.490e-05 mW/um2 | 1.63x |

## What limits these numbers

The 45nm library defines nine wire load models, and the 15nm library defines
none, so the 15nm run carries no estimated interconnect. A control run of the
45nm design at 500 MHz with `set auto_wire_load_selection false` gives
697.452 um2 and 0.0223 ns of slack, against 697.452 um2 and 0.0190 ns with
the model. The difference is 3 ps of slack and no area, so the wire load
model does not bias this comparison at this design size.

Neither run holds real interconnect parasitics, because the flow stops at the
netlist and runs no place and route. Wire delay and wire capacitance grow in
importance as the node shrinks, so the 6.7x frequency ratio and the 3.4x
power ratio are both optimistic for the 15nm library. Treat them as an upper
bound on the gain, not as a silicon result.

The 15nm library is a predictive, non-manufacturable library built on the
NCSU FreePDK15 process. Its numbers describe a model of a 15nm process, not a
foundry process.
