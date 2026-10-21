"""Read the ports, the clocks, and the asynchronous resets of the top module from a DC netlist.

The netlist is <design>_mapped.v of step 2. DC writes it with `change_names -rules verilog`, so
its port declarations have a simple form. The clock and the reset come from the cell pins in the
NanGate 15nm library:
    CLK     the clock pin of the flip-flops (DFFRNQ, DFFSNQ, SDFF*) and of the clock gate
            (CLKGATETST_X1, inside the SNPS_CLOCK_GATE modules)
    RN, SN  the active-low asynchronous reset and set pins of the flip-flops
    INV_X*  pins I -> ZN (inverts), BUF_X* and CLKBUF_X*: pins I -> Z
"""
import re

DECL_RE = re.compile(r"^\s*(input|output|inout)\s+(?:\[(\d+):(\d+)\]\s*)?([^;]+);", re.M)
PIN_RE = re.compile(r"\.(CLK|RN|SN)\(\s*([^()\s]+)\s*\)")
CELL_RE = re.compile(r"^\s*(INV|BUF|CLKBUF)_X\d+\s+\S+\s*\(([^;]*)\);", re.M)
CONN_RE = re.compile(r"\.(\w+)\(\s*([^()\s]+)\s*\)")

# Names of synchronous or asynchronous reset ports. The flags make the match independent of case.
RESET_NAME_RE = re.compile(r"^(?:i_|in_)?(?:a|s)?(?:rst|reset|rstn|resetn|nrst|nreset)(?:_?n|_?b|_?l)?(?:_?i|_in)?$",
                           re.I)
ACTIVE_LOW_NAME_RE = re.compile(r"(?:^n|n$|_n$|_b$|b$|_l$|_ni$|n_i$|n_in$)", re.I)


class NetlistError(Exception):
    """The netlist has no top module of the given name."""


def top_text(netlist_text, top):
    """Return the text of the top module, from 'module <top> (' to 'endmodule'."""
    m = re.search(rf"^module\s+{re.escape(top)}\s*\(", netlist_text, re.M)
    if not m:
        raise NetlistError(f"module {top} is not in the netlist")
    end = netlist_text.find("endmodule", m.end())
    if end < 0:
        raise NetlistError(f"module {top} has no endmodule")
    return netlist_text[m.start():end]


def ports(netlist_text, top):
    """Return the ports of the top module: a list of dicts (name, direction, width, msb, lsb)."""
    text = top_text(netlist_text, top)
    out = []
    for m in DECL_RE.finditer(text):
        direction, msb, lsb, names = m.groups()
        for name in (n.strip() for n in names.split(",")):
            if not name:
                continue
            width = abs(int(msb) - int(lsb)) + 1 if msb is not None else 1
            out.append({"name": name, "direction": direction, "width": width,
                        "msb": int(msb) if msb is not None else None,
                        "lsb": int(lsb) if lsb is not None else None})
    return out


def _drivers(text):
    """Map each output net of an inverter or a buffer to (input net, inverts)."""
    drivers = {}
    for m in CELL_RE.finditer(text):
        kind, body = m.group(1), m.group(2)
        conn = dict(CONN_RE.findall(body))
        if kind == "INV" and "I" in conn and "ZN" in conn:
            drivers[conn["ZN"]] = (conn["I"], True)
        elif kind in ("BUF", "CLKBUF") and "I" in conn and "Z" in conn:
            drivers[conn["Z"]] = (conn["I"], False)
    return drivers


def clocks_and_resets(netlist_text, top):
    """Return (clock ports, reset ports) of the top module.

    clock ports  the inputs that connect to a CLK pin
    reset ports  {port: {"pin": "RN" or "SN", "active_low": bool}} for each input that drives an RN
                 or SN pin, directly or through up to 4 inverters and buffers
    """
    text = top_text(netlist_text, top)
    inputs = {p["name"] for p in ports(netlist_text, top) if p["direction"] == "input"}
    drivers = _drivers(text)
    clocks, resets = set(), {}
    for pin, net in PIN_RE.findall(text):
        if pin == "CLK":
            if net in inputs:
                clocks.add(net)
            continue
        inverts = False
        for _hop in range(5):
            if net in inputs:
                # RN and SN are active low. An odd number of inverters makes the port active high.
                resets.setdefault(net, {"pin": pin, "active_low": not inverts})
                break
            if net not in drivers:
                break
            net, inv = drivers[net]
            inverts ^= inv
    return sorted(clocks), resets


def reset_by_name(port_names):
    """Return (port, active_low) for the first port whose name looks like a reset, or None."""
    for name in port_names:
        if RESET_NAME_RE.match(name):
            return name, bool(ACTIVE_LOW_NAME_RE.search(name))
    return None
