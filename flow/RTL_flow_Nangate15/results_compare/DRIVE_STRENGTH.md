# Does the area rise and do the cells grow when the frequency rises?

Yes, both happen, and both need a load on the design. The drive strength of
every instance comes from the `_X` suffix in `<design>_mapped.v`.

Every run below uses a load on the outputs and a driver on the inputs:

```bash
TECH=nangate15 CLOCK_FREQ_MHZ=3500 OUTPUT_LOAD_FF=20 DRIVING_CELL=BUF_X4 \
    RESULTS_DIR=$PWD/results_fs15_3500 ./02_synth.sh
```

## NanGate 15nm, frequency sweep, 20 fF on each output

| Frequency | Cell area | Leaf cells | Average drive | Histogram |
| --- | --- | --- | --- | --- |
| 500 MHz | 159.646 um2 | 360 | 1.00 | X1:360 |
| 1500 MHz | 159.646 um2 | 360 | 1.00 | X1:360 |
| 2500 MHz | 161.513 um2 | 367 | 1.03 | X1:361, X2:4, X4:2 |
| 3500 MHz | 178.717 um2 | 422 | 1.06 | X1:398, X2:24 |
| 4500 MHz | 183.091 um2 | 456 | 1.04 | X1:442, X2:13, X8:1 |
| 5500 MHz | 190.710 um2 | 505 | 1.04 | X1:493, X2:11, X8:1 |
| 6500 MHz | 226.050 um2 | 670 | 1.18 | X1:585, X2:75, X4:6, X8:4 |

The area rises by 1.42x from 500 MHz to 6500 MHz, and the cell count rises by
1.86x. The last row misses timing by 9.3 ps, so it shows what the tool does
when it cannot reach the target.

The area is flat up to 1500 MHz, because the constraint does not bind there.
The rise starts at 2500 MHz, which is where the clock first costs something.

## The larger cells are real logic, not only buffers

At 6500 MHz the cells above X1 are:

```
NAND2_X2:20  NOR2_X2:12  OAI22_X2:12  OAI21_X2:11  AOI21_X2:6
OR2_X2:3     AND2_X2:1
BUF_X2:4  BUF_X4:3  INV_X2:4  INV_X4:2  CLKBUF_X2:2  CLKBUF_X4:1  CLKBUF_X8:4
```

Design Compiler upsizes the logic itself, not the buffers alone. At 2500 MHz
only 4 cells sit above X1, and at 6500 MHz there are 85.

X2 is the ceiling for logic at 15nm, because that library holds every gate in
X1 and X2 only. X4, X8, and X16 exist for `INV`, `BUF`, `CLKBUF`, and `TBUF`
alone, so the higher numbers in the histogram are always drive cells.

## NanGate 45nm, frequency sweep, 20 fF on each output

| Frequency | Cell area | Leaf cells | Average drive | Histogram |
| --- | --- | --- | --- | --- |
| 200 MHz | 596.638 um2 | 328 | 1.01 | X1:326, X2:2 |
| 400 MHz | 703.570 um2 | 457 | 1.00 | X1:456, X2:1 |
| 600 MHz | 698.782 um2 | 443 | 1.01 | X1:439, X2:4 |
| 800 MHz | 752.780 um2 | 505 | 1.02 | X1:494, X2:11 |

The area rises by 1.26x, and the count of cells above X1 rises from 2 to 11.

## The load decides how large the cells grow

NanGate 45nm at 800 MHz, with the load as the only change:

| Output load | Cell area | Average drive | Histogram |
| --- | --- | --- | --- |
| 20 fF | 752.780 um2 | 1.02 | X1:494, X2:11 |
| 100 fF | 786.296 um2 | 1.08 | X1:470, X2:41 |
| 400 fF | 925.414 um2 | 2.00 | X1:447, X2:33, X16:32 |

At 400 fF the tool places 32 `BUF_X16` cells, one per bit of `acc_o[31:0]`,
and it also raises the 32 flip-flops to `DFFS_X2`. The area grows by 1.23x
over the 20 fF run at the same frequency.

## Why the frequency alone moves the area more than the drive strength

Design Compiler has two ways to gain speed: shorten the logic, or drive it
harder. Driving harder pays only when a net carries real capacitance. With a
light load, the cheaper move is to shorten the logic, so the cell count rises
faster than the drive strength. With a heavy load, the tool must upsize,
because no amount of restructuring drives 400 fF.

Both responses raise the area, which is the expected result.

## The settings

`config.sh` holds `OUTPUT_LOAD_FF` and `DRIVING_CELL`. Both are empty by
default, which keeps the earlier results valid. Both libraries state
capacitance in femtofarad, so the load needs no conversion, and both hold the
cell `BUF_X4`.

With both empty the design drives nothing, the area and the power are
optimistic, and the drive strength stays at X1 across most of the frequency
range. Set them to model the load your outputs really see.
