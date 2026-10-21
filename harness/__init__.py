"""JEV_RTL harness.

The harness turns RTL designs into questions with correct answers. Every correct answer comes from
MV's flow in flow/RTL_flow_Nangate15. The harness never changes a file of that flow. It runs the
flow in a separate run folder for each design.

Modules:
    paths       the fixed paths and constants
    flow        make a run folder and run one step of the flow
    synthcheck  decide from a DC log if a design synthesizes, and the reason if not
    netlist     read the ports, the clock, and the resets from a DC netlist
    tbgen       fill a REvolution power testbench, or write a new one
    sources     read the designs of each dataset
    labels      run the flow for a list of designs and store the results
    selftest    checks that need no tool run

Run it with Python 3.12 from the folder JEV_RTL:
    python3.12 -m harness --help
"""
