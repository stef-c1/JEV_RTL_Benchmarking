"""Power testbenches for the flow.

Two cases:
1. A REvolution design has a template tb_pt_<design>.sv. fill_revolution_tb fills its
   placeholders for MV's flow and changes nothing else.
2. Another design gets a new testbench from write_tb, in the same style as the REvolution templates:
   the same seed, the same cycle counts, a new random value on each data input in every cycle, and
   a random reset in about 1 of 32 cycles.

The flow defines the macro CLK_PERIOD_NS, and it reads the VCD file power.vcd from the folder in
which the simulator runs (see flow/RTL_flow_Nangate15/tb/README.md).
"""
import re

from .flow import PowerTB

CLK_GUARD = "`ifndef CLK_PERIOD_NS\n  `define CLK_PERIOD_NS 2.0\n`endif\n"
SEED = "32'hC0DE0042"
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SV_KEYWORDS = {"input", "output", "inout", "logic", "wire", "reg", "module", "begin", "end",
               "int", "real", "time", "string", "event", "always", "initial", "task", "do"}


class TBError(Exception):
    """The harness cannot make a testbench for this design."""


def fill_revolution_tb(template_text, top):
    """Fill a REvolution tb_pt template for MV's flow. Return a PowerTB.

    Changes:
      {CLK_HALF}                     -> `CLK_PERIOD_NS / 2.0
      $dumpfile("<template path>")   -> $dumpfile("power.vcd")
      a guard for CLK_PERIOD_NS after the timescale line
    All other text stays the same.
    """
    text = template_text
    if text.count("{CLK_HALF}") != 1:
        raise TBError("the template must have {CLK_HALF} exactly once")
    text = text.replace("{CLK_HALF}", "`CLK_PERIOD_NS / 2.0")
    text, n = re.subn(r'\$dumpfile\("[^"]*"\)', '$dumpfile("power.vcd")', text)
    if n != 1:
        raise TBError(f"the template must have one $dumpfile call, it has {n}")
    text, n = re.subn(r"^(`timescale[^\n]*\n)", lambda m: m.group(1) + CLK_GUARD, text, count=1,
                      flags=re.M)
    if n != 1:
        raise TBError("the template has no `timescale line")
    left = re.findall(r"\{[A-Z_]+\}", text)
    if left:
        raise TBError(f"placeholders remain in the template: {sorted(set(left))}")
    m = re.search(r"^\s*module\s+(\w+)\s*;", text, re.M)
    if not m:
        raise TBError("the template has no module line")
    module = m.group(1)
    inst = re.search(rf"^\s*{re.escape(top)}\s+(\w+)\s*\(", text, re.M)
    if not inst:
        raise TBError(f"the template has no instance of {top}")
    return PowerTB(module=module, text=text, dut_instance=inst.group(1))


def write_tb(top, ports, clock, reset=None, reset_active_low=True):
    """Write a power testbench for a design with no template. Return a PowerTB.

    top     the top module
    ports   the ports from netlist.ports (name, direction, width)
    clock   the clock port, or "" for a combinational design
    reset   the reset port, or None
    """
    names = [p["name"] for p in ports]
    for name in names:
        if not IDENT_RE.match(name) or name in SV_KEYWORDS or name.startswith("_"):
            raise TBError(f"port name not supported: {name}")
    if any(p["direction"] == "inout" for p in ports):
        raise TBError("inout ports are not supported")
    if clock and clock not in names:
        raise TBError(f"the clock {clock} is not a port")
    if reset and reset not in names:
        raise TBError(f"the reset {reset} is not a port")
    module = f"tb_power_{top}"
    # Sort the ports by name: two designs with the same ports then get the same testbench text,
    # also if DC writes the ports in another order.
    ports = sorted(ports, key=lambda p: p["name"])
    names = [p["name"] for p in ports]
    data_inputs = [p for p in ports if p["direction"] == "input" and p["name"] not in (clock, reset)]
    max_width = max([32] + [p["width"] for p in data_inputs])
    active = "1'b0" if reset_active_low else "1'b1"
    inactive = "1'b1" if reset_active_low else "1'b0"

    def decl(p):
        rng = f"[{p['width'] - 1}:0] " if p["width"] > 1 else ""
        return f"  logic {rng}{p['name']};"

    lines = ["`timescale 1ns/1ps", CLK_GUARD.rstrip("\n"),
             "// Power testbench written by the JEV_RTL harness, in the style of the REvolution",
             "// tb_pt templates: seed 32'hC0DE0042, 8 reset cycles, 16 warm-up cycles, 4000 measured",
             "// cycles, a new random value on each data input in every cycle.",
             f"module {module};",
             "  localparam real CLK_HALF = `CLK_PERIOD_NS / 2.0;",
             "  localparam int  N_PT = 4000;",
             "  localparam int  PT_WARMUP_CYCLES = 16;",
             "  localparam int  RESET_CYCLES = 8;"]
    if not clock:
        lines.append("  logic _tb_clk;   // paces the inputs, not a port of the design")
    lines += [decl(p) for p in ports]
    lines.append(f"  logic [{max_width - 1}:0] _rnd;")
    pace = clock or "_tb_clk"
    lines.append(f"  always #(CLK_HALF) {pace} = ~{pace};")
    conns = ",\n".join(f"    .{n}({n})" for n in names)
    lines += [f"  {top} dut (", conns, "  );", "  task automatic drive_inputs();"]
    for p in data_inputs:
        words = (p["width"] + 31) // 32
        lines += ["    _rnd = '0;",
                  f"    for (int _i = 0; _i < {words}; _i++) _rnd = (_rnd << 32) | $urandom();",
                  f"    {p['name']} = _rnd[{p['width'] - 1}:0];" if p["width"] > 1
                  else f"    {p['name']} = _rnd[0];"]
    if reset:
        lines.append(f"    {reset} = (($urandom % 32) == 0) ? {active} : {inactive};")
    lines += ["  endtask", "  initial begin", f"    void'($urandom({SEED}));", f"    {pace} = 1'b0;"]
    lines += [f"    {p['name']} = '0;" for p in data_inputs]
    if reset:
        lines += [f"    {reset} = {active};", f"    repeat (RESET_CYCLES) @(negedge {pace});",
                  f"    {reset} = {inactive};"]
    else:
        lines.append(f"    repeat (RESET_CYCLES) @(negedge {pace});")
    lines += [f"    for (int _k = 0; _k < PT_WARMUP_CYCLES; _k++) begin @(negedge {pace}); drive_inputs(); end",
              '    $dumpfile("power.vcd");',
              f"    $dumpvars(0, {module});",
              "    $dumpon;",
              f"    for (int _k = 0; _k < N_PT; _k++) begin @(negedge {pace}); drive_inputs(); end",
              "    $dumpoff;",
              "    $finish;",
              "  end",
              f'  initial begin #(CLK_HALF * 2 * (N_PT + PT_WARMUP_CYCLES + RESET_CYCLES + 200)); $display("{module} TIMEOUT"); $finish; end',
              "endmodule", ""]
    return PowerTB(module=module, text="\n".join(lines), dut_instance="dut")
