# tools/

One setup file per tool release. Each file puts its tool on the `PATH` and
sets its license server. Section 0 of `../config.sh` names the three files the
flow sources, and in that order:

```bash
TOOL_ENV_FILES=(
    "tools/questasim_2022.4.rc"
    "tools/syn_vU-2022.12-SP2.rc"
    "tools/pt_vU-2022.12-SP2.rc"
)
```

## Another release

Change the file name in that list. The folder holds two releases of the two
Synopsys tools:

| Tool | 2022.12, the tested release | 2024.09 |
| --- | --- | --- |
| QuestaSim | `questasim_2022.4.rc` | |
| Design Compiler | `syn_vU-2022.12-SP2.rc` | `syn_vW-2024.09-SP5.rc` |
| PrimeTime | `pt_vU-2022.12-SP2.rc` | `pt_vW-2024.09-SP5.rc` |

Use one release of Design Compiler and the matching release of PrimeTime. A
setup file adds its folders at the end of the `PATH`, so a shell that holds
another release already would win. The flow moves the folders of the release
you name to the front, and `../00_check.sh` prints the full path of each tool
it found, so you see which one runs.

## Another machine

The paths in these files are the ones that work at ESAT. When a tool sits
somewhere else, open its file and correct every install folder in it. The
number of lines differs per file, because a file repeats the path where it
needs it:

| File | Lines that hold the install folder |
| --- | --- |
| `questasim_2022.4.rc` | `MGC_QUESTA_HOME`, 1 line |
| `syn_vU-2022.12-SP2.rc` | `SYNOPSYS`, `SYNOPSYS_ROOT`, `SYNOPSYS_SYN_ROOT`, and `SYNOPSYS_LC_ROOT`, which names the Library Compiler release, 4 lines |
| `pt_vU-2022.12-SP2.rc` | `SYNOPSYS`, 1 line |

The `PATH` line of each file needs no edit, because it builds on the variable
above it. The license servers are `MGLS_LICENSE_FILE` for QuestaSim and
`SNPSLMD_LICENSE_FILE` for the two Synopsys tools.

Run `../00_check.sh` after a change. It reports a tool that is still missing.

## Your own setup file

A file here is a plain bash file, and the flow sources it. A C shell file does
not work, and the flow says so by name when it finds one.
