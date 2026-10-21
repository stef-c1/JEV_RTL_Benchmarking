#!/usr/bin/env python3
"""Probe which RTL constructs Design Compiler rejects.

Each probe is one small module `top` with one construct. The script runs
QuestaSim `vlog` (is the code legal for simulation?) and Design Compiler
(analyze, elaborate, link, compile_ultra) on each probe. It writes one CSV
row per probe with the error and warning message IDs of each tool.

The result decides which classes the synth_why test can use: a class is
valid only if DC reports an error for it.

Usage:  python3 probes/synth_classes.py [work_dir]
The work directory (default /tmp/jev_synth_probes) holds the logs.
The CSV goes next to this script.
"""
import csv
import os
import re
import subprocess
import sys
import time

FLOW = "/users/micas/scuycken/Synthesis_scripts/RTL_flow_FreePDK15"
DB = f"{FLOW}/tech/nangate15/NanGate_15nm_OCL_typical_conditional_nldm.db"
ENV = (f"source {FLOW}/tools/questasim_2022.4.rc; "
       f"source {FLOW}/tools/syn_vU-2022.12-SP2.rc; ")

HDR = "module top(input clk, input rst, input [7:0] d, output reg [7:0] q);\n"
END = "endmodule\n"
SEQ = "  always @(posedge clk or posedge rst)\n    if (rst) q <= 8'd0; else q <= q + d;\n"

PROBES = {
    # controls: expected to synthesize
    "c00_clean": HDR + SEQ + END,
    "c01_display": HDR + "  always @(posedge clk) begin q <= d; $display(\"%d\", d); end\n" + END,
    "c02_latch": HDR + "  always @(*) if (d[0]) q = d;\n" + END,
    "c03_comb_loop": HDR + "  wire a;\n  assign a = ~a & d[0];\n  always @(posedge clk) q <= {7'd0, a};\n" + END,
    "c04_division": HDR + "  always @(posedge clk) q <= d / {4'd0, d[3:0]};\n" + END,
    "c05_assign_delay": HDR + "  wire [7:0] w;\n  assign #5 w = d;\n  always @(posedge clk) q <= w;\n" + END,
    "c06_nb_delay": HDR + "  always @(posedge clk) q <= #2 d;\n" + END,
    "c07_initial": HDR + "  initial q = 8'h00;\n  always @(posedge clk) q <= q + d;\n" + END,
    "c08_x_compare": HDR + "  always @(posedge clk) if (d === 8'bx) q <= 8'd1; else q <= d;\n" + END,
    "c09_assign_to_reg": HDR + "  assign q = d;\n" + END,
    # candidate non-synthesizable constructs
    "p01_syntax_error": HDR + "  always @(posedge clk) begin q <= d end\n" + END,
    "p02_undeclared": HDR + "  always @(posedge clk) q <= d + undeclared_sig;\n" + END,
    "p03_missing_module": HDR + "  wire [7:0] w;\n  sub u0(.a(d), .y(w));\n  always @(posedge clk) q <= w;\n" + END,
    "p04_delay_stmt": HDR + "  always @(posedge clk) begin #2 q <= d; end\n" + END,
    "p05_wait": HDR + "  always @(posedge clk) begin wait (rst == 1'b0); q <= d; end\n" + END,
    "p06_multi_event": HDR + "  always begin\n    @(posedge clk) q <= d;\n    @(posedge clk) q <= ~d;\n  end\n" + END,
    "p07_both_edges": HDR + "  always @(posedge clk or negedge clk) q <= d;\n" + END,
    "p08_multi_driver": HDR + "  always @(posedge clk) q <= d;\n  always @(posedge clk) if (rst) q <= 8'd0;\n" + END,
    "p09_while_data": HDR + "  reg [7:0] x, n;\n  always @(*) begin\n    x = d; n = 0;\n    while (x != 0) begin x = x >> 1; n = n + 1; end\n  end\n  always @(posedge clk) q <= n;\n" + END,
    "p10_for_var_bound": HDR + "  integer i; reg [7:0] acc;\n  always @(*) begin\n    acc = 0;\n    for (i = 0; i < d; i = i + 1) acc = acc + 1;\n  end\n  always @(posedge clk) q <= acc;\n" + END,
    "p11_real": HDR + "  real r;\n  always @(posedge clk) begin r = d * 1.5; q <= r; end\n" + END,
    "p12_fork": HDR + "  always @(posedge clk) fork q <= d; join\n" + END,
    "p13_force": HDR + "  always @(posedge clk) if (rst) force q = 8'd0; else release q;\n" + END,
    "p14_random": HDR + "  always @(posedge clk) q <= $random;\n" + END,
    "p15_async_if_not_top": HDR + "  always @(posedge clk or posedge rst) begin\n    q <= d;\n    if (rst) q <= 8'd0;\n  end\n" + END,
    "p16_edge_level_mix": HDR + "  always @(posedge clk or d[0]) q <= d;\n" + END,
    "p17_hier_ref": "module sub(input clk, input [7:0] d);\n  reg [7:0] r;\n  always @(posedge clk) r <= d;\nendmodule\n"
                    + HDR + "  sub u0(.clk(clk), .d(d));\n  always @(posedge clk) q <= u0.r;\n" + END,
    "p18_class": HDR + "  class C; int x; endclass\n  C obj;\n  always @(posedge clk) begin obj = new; q <= d; end\n" + END,
    "p19_dyn_array": HDR + "  int da[];\n  always @(posedge clk) begin da = new[4]; q <= da.size(); end\n" + END,
    "p20_string": HDR + "  string s;\n  always @(posedge clk) begin s = \"ab\"; q <= s.len(); end\n" + END,
    "p21_recursion_var": HDR + "  function automatic [7:0] f(input [7:0] n);\n    f = (n <= 1) ? 8'd1 : n * f(n - 1);\n  endfunction\n  always @(posedge clk) q <= f(d);\n" + END,
    "p22_mixed_blocking": HDR + "  always @(posedge clk) begin q = d; q <= q + 1; end\n" + END,
    "p23_proc_to_wire": "module top(input clk, input rst, input [7:0] d, output [7:0] q);\n  wire [7:0] w;\n  always @(posedge clk) w <= d;\n  assign q = w;\n" + END,
    "p24_task_delay": HDR + "  task t(input [7:0] a); begin #1 q = a; end endtask\n  always @(posedge clk) t(d);\n" + END,
    "p25_event": HDR + "  event e;\n  always @(posedge clk) -> e;\n  always @(e) q <= d;\n" + END,
    "p26_two_clocks": "module top(input clk, input clk2, input rst, input [7:0] d, output reg [7:0] q);\n  always @(posedge clk or posedge clk2) q <= d;\n" + END,
    "p27_async_data_load": HDR + "  always @(posedge clk or posedge rst)\n    if (rst) q <= d; else q <= q + 8'd1;\n" + END,
    "p28_proc_assign": HDR + "  always @(posedge clk) if (rst) assign q = 8'd0; else deassign q;\n" + END,
    "p29_forever_no_timing": HDR + "  always @(*) forever q = d;\n" + END,
    "p30_repeat_var": HDR + "  reg [7:0] acc;\n  always @(*) begin acc = 0; repeat (d) acc = acc + 1; end\n  always @(posedge clk) q <= acc;\n" + END,
    "p31_udp": "primitive myand(out, a, b);\n  output out; input a, b;\n  table\n    1 1 : 1;\n    0 ? : 0;\n    ? 0 : 0;\n  endtable\nendprimitive\n"
               + HDR + "  wire w;\n  myand g0(w, d[0], d[1]);\n  always @(posedge clk) q <= {7'd0, w};\n" + END,
    "p32_always_no_event": HDR + "  always q = d;\n" + END,
    "p33_dpi": HDR + "  import \"DPI-C\" function int cf(int a);\n  always @(posedge clk) q <= cf(d);\n" + END,
    "p34_trireg": HDR + "  trireg [7:0] t;\n  assign t = d[0] ? d : 8'bz;\n  always @(posedge clk) q <= t;\n" + END,
    "p35_negedge_level_reset_mix": HDR + "  always @(posedge clk or rst) if (rst) q <= 8'd0; else q <= d;\n" + END,
    "p36_var_part_select": HDR + "  always @(posedge clk) q <= d[d[2:0]:0];\n" + END,
    "p37_mult_in_sens_task": HDR + "  always @(posedge clk) begin q <= d; @(negedge clk) q <= ~d; end\n" + END,
    "p38_fileio": HDR + "  integer fd;\n  always @(posedge clk) begin fd = $fopen(\"x.txt\"); q <= d; end\n" + END,
    "p39_time_var": HDR + "  time t;\n  always @(posedge clk) begin t = $time; q <= t[7:0]; end\n" + END,
    "p40_unknown_port": "module sub(input [7:0] a, output [7:0] y);\n  assign y = ~a;\nendmodule\n"
                        + HDR + "  wire [7:0] w;\n  sub u0(.b(d), .y(w));\n  always @(posedge clk) q <= w;\n" + END,
    "p41_unknown_param": "module sub(input [7:0] a, output [7:0] y);\n  assign y = ~a;\nendmodule\n"
                         + HDR + "  wire [7:0] w;\n  sub #(.W(8)) u0(.a(d), .y(w));\n  always @(posedge clk) q <= w;\n" + END,
}

DC_TCL = """set sh_continue_on_error true
set target_library [list "{db}"]
set link_library [list * "{db}"]
analyze -format sverilog [list {{{src}}}]
elaborate top
current_design top
link
if {{[sizeof_collection [get_ports -quiet clk]] > 0}} {{
  create_clock [get_ports clk] -name CORE_CLK -period 1000
}}
compile_ultra -gate_clock
report_area
exit
"""

ID_RE = re.compile(r"\(([A-Z]+-\d+)\)")


def ids(lines, kind):
    """Return the sorted message IDs of the lines that start with kind."""
    out = set()
    for line in lines:
        if line.startswith(kind):
            m = ID_RE.search(line)
            out.add(m.group(1) if m else "noid")
    return sorted(out)


def sh(cmd):
    r = subprocess.run(["bash", "-c", ENV + cmd],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    return r.returncode, r.stdout


def run_probe(name, work, retries=30, wait_s=60):
    """Run vlog and DC on one probe. Keep a valid DC log from an earlier run.

    DC runs one at a time, because the license server is shared. If no
    DC license is free (SEC-50), wait and try again.
    """
    d = os.path.join(work, name)
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, name + ".sv")
    with open(src, "w") as f:
        f.write(PROBES[name])
    # QuestaSim compile: is the code legal for simulation?
    rc, out = sh("cd {0} && rm -rf work && vlib work >/dev/null 2>&1; vlog -sv {1}".format(d, src))
    with open(os.path.join(d, "vlog.log"), "w") as f:
        f.write(out)
    vlog_err = [l for l in out.splitlines() if l.startswith("** Error")]
    # Design Compiler
    log_path = os.path.join(d, "dc.log")
    old = open(log_path).read() if os.path.exists(log_path) else ""
    if not old or "(SEC-50)" in old or "Total cell area" not in old and "Error" not in old:
        tcl = os.path.join(d, "dc.tcl")
        with open(tcl, "w") as f:
            f.write(DC_TCL.format(db=DB, src=src))
        for _ in range(retries):
            _, log = sh("cd {0} && dc_shell -f {1} < /dev/null".format(d, tcl))
            if "(SEC-50)" not in log:
                break
            time.sleep(wait_s)
        with open(log_path, "w") as f:
            f.write(log)
    else:
        log = old
    lines = log.splitlines()
    m = re.search(r"^Total cell area:\s+(\S+)", log, re.M)
    first_err = next((l for l in lines if l.startswith("Error")), "")
    return {
        "probe": name,
        "vlog_ok": "yes" if (rc == 0 and not vlog_err) else "no",
        "vlog_error": vlog_err[0][:160] if vlog_err else "",
        "dc_errors": " ".join(ids(lines, "Error")),
        "dc_warnings": " ".join(ids(lines, "Warning")),
        "dc_area_um2": m.group(1) if m else "",
        "dc_first_error": first_err[:200],
    }


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else "/tmp/jev_synth_probes"
    os.makedirs(work, exist_ok=True)
    rows = []
    for n in PROBES:
        rows.append(run_probe(n, work))
        r = rows[-1]
        print("{0:28s} vlog={1:3s} dc_err=[{2}] area={3}".format(
            r["probe"], r["vlog_ok"], r["dc_errors"], r["dc_area_um2"]), flush=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synth_classes_results.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("CSV:", out)


if __name__ == "__main__":
    main()
