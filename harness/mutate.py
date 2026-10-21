"""Mutants for synth_reason and synth_yesno.

A mutant is a real design that synthesizes, with exactly one edit. Each template makes the edit of
one class of notes/synth_reason.md at one place, selected with a seeded random generator. The
template only proposes the edit: the DC run of the label job decides the class, and the builder
keeps a mutant only if DC shows the intended class (synthcheck.classify).

The templates search a copy of the text in which the comments and the strings are blanked with
spaces. Thus an edit never lands inside a comment, and the positions are the same in both texts.

The trap templates (TRAP_TEMPLATES) make edits that DC accepts although a common rule of thumb
says "not synthesizable", for example an `initial` block or a `#` delay (notes/synth_yesno.md).
"""
import random
import re

ID = r"[A-Za-z_]\w*"


def blank_comments(text):
    """Return text with comments and strings replaced by spaces (the newlines stay)."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(n, j + 1)
        else:
            i += 1
            continue
        for k in range(i, j):
            if out[k] != "\n":
                out[k] = " "
        i = j
    return "".join(out)


def _apply(text, start, end, new):
    return text[:start] + new + text[end:]


def _block_end(masked, begin_pos):
    """Return the position after the 'end' that matches the 'begin' at begin_pos, or -1."""
    depth = 0
    for m in re.finditer(r"\b(begin|end|fork|join)\b", masked[begin_pos:]):
        word = m.group(1)
        if word in ("begin", "fork"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return begin_pos + m.end()
    return -1


def _clocked_blocks(masked):
    """Yield (match) for each `always @(posedge X ...)` with only edge events."""
    return list(re.finditer(rf"always\s*@\s*\(\s*(posedge|negedge)\s+({ID})((?:\s*(?:or|,)\s*(?:posedge|negedge)\s+{ID})*)\s*\)",
                            masked))


def _inputs(masked):
    """Return the input names. A list such as 'input d, output reg q' ends at 'output'."""
    names = []
    for m in re.finditer(rf"\binput\b((?:\s*(?:wire|reg|logic|signed|unsigned|\[[^\]]*\]))*\s*{ID}(?:\s*,\s*(?!(?:input|output|inout)\b){ID})*)", masked):
        body = re.sub(r"\[[^\]]*\]", " ", m.group(1))
        for w in re.findall(ID, body):
            if w in ("output", "inout"):
                break
            if w not in ("wire", "reg", "logic", "signed", "unsigned", "input") and w not in names:
                names.append(w)
    return names


def _nb_assigns(masked):
    """Nonblocking assignments `x <= expr;` with a plain name x."""
    return list(re.finditer(rf"(?<![<>=!])\b({ID})\s*<=\s*([^;]+);", masked))


# ---------------------------------------------------------------- the templates of each class
# Each template is f(text, masked, rng) -> (new text, description) or None.

def t_drop_semicolon(text, masked, rng):
    sites = [m for m in re.finditer(r"\bassign\b[^;]*;", masked)] + _nb_assigns(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    pos = masked.index(";", m.start())
    return _apply(text, pos, pos + 1, ""), f"removed the ';' at offset {pos}"


def t_misspell_rhs(text, masked, rng):
    sites = []
    for m in _nb_assigns(masked):
        rhs_start = m.start(2)
        for w in re.finditer(ID, m.group(2)):
            before = m.group(2)[w.start() - 1] if w.start() > 0 else " "
            if w.group(0) in ("begin", "end") or before in "'$`" or before.isdigit():
                continue      # not a number such as 8'hFF, a system function, or a macro
            sites.append((rhs_start + w.start(), rhs_start + w.end(), w.group(0)))
    if not sites:
        return None
    s, e, word = rng.choice(sites)
    new = word + "_x"
    return _apply(text, s, e, new), f"renamed one use of '{word}' to the undeclared name '{new}'"


def t_integer_to_real(text, masked, rng):
    sites = list(re.finditer(rf"\binteger\s+(?={ID})", masked))
    if not sites:
        return None
    m = rng.choice(sites)
    return _apply(text, m.start(), m.end(), "real "), "changed an 'integer' declaration to 'real'"


def t_reg_to_time(text, masked, rng):
    sites = [m for m in re.finditer(rf"\breg\s*(\[\s*(\d+)\s*:\s*0\s*\])?\s*(?={ID}\s*[;,=])", masked)
             if not m.group(2) or int(m.group(2)) <= 63]
    if not sites:
        return None
    m = rng.choice(sites)
    return _apply(text, m.start(), m.end(), "time "), "changed a 'reg' declaration to 'time'"


def t_wait(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if re.match(r"\s*begin\b", masked[b.end():])]
    ins = _inputs(masked)
    if not blocks or not ins:
        return None
    b = rng.choice(blocks)
    pos = b.end() + re.match(r"\s*begin\b", masked[b.end():]).end()
    sig = rng.choice([n for n in ins if n != b.group(2)] or ins)
    return _apply(text, pos, pos, f"\n    wait ({sig});"), f"inserted 'wait ({sig});' at the start of a clocked block"


def t_fork_join(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if re.match(r"\s*begin\b", masked[b.end():])]
    if not blocks:
        return None
    b = rng.choice(blocks)
    begin_pos = b.end() + re.match(r"\s*", masked[b.end():]).end()
    end_pos = _block_end(masked, begin_pos)
    if end_pos < 0:
        return None
    new = text[:begin_pos] + "fork" + text[begin_pos + 5:end_pos - 3] + "join" + text[end_pos:]
    return new, "changed the 'begin'/'end' of a clocked block to 'fork'/'join'"


def t_random(text, masked, rng):
    sites = _nb_assigns(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    return _apply(text, m.start(2), m.end(2), "$random"), f"changed the value of '{m.group(1)} <=' to $random"


def t_force(text, masked, rng):
    sites = _nb_assigns(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    return (_apply(text, m.start(), m.end(), f"force {m.group(1)} = {text[m.start(2):m.end(2)]};"),
            f"changed '{m.group(1)} <= ...' to 'force {m.group(1)} = ...'")


def t_both_edges(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if not b.group(3).strip()]
    if not blocks:
        return None
    b = rng.choice(blocks)
    other = "negedge" if b.group(1) == "posedge" else "posedge"
    new_ev = f"always @({b.group(1)} {b.group(2)} or {other} {b.group(2)})"
    return _apply(text, b.start(), b.end(), new_ev), f"added '{other} {b.group(2)}' to an event list"


def t_edge_level(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if not b.group(3).strip()]
    ins = [n for n in _inputs(masked)]
    if not blocks or not ins:
        return None
    b = rng.choice(blocks)
    sig = rng.choice([n for n in ins if n != b.group(2)] or ins)
    new_ev = f"always @({b.group(1)} {b.group(2)} or {sig})"
    return _apply(text, b.start(), b.end(), new_ev), f"added the level event '{sig}' to an edge event list"


def _async_blocks(masked):
    return [b for b in _clocked_blocks(masked) if b.group(3).strip()]


def t_reset_to_data(text, masked, rng):
    ins = _inputs(masked)
    sites = []
    for b in _async_blocks(masked):
        m = re.match(r"\s*(?:begin\s*)?if\s*\(([^)]*)\)\s*(?:begin\s*)?", masked[b.end():])
        if not m:
            continue
        start = b.end() + m.end()
        a = re.match(rf"({ID})\s*<=\s*([^;]+);", masked[start:])
        if a and re.fullmatch(r"\s*(?:\d+'[bdhoBDHO][0-9a-fA-F_xXzZ]+|\d+|'0|'1|\{[^}]*\})\s*", a.group(2)):
            sites.append((start + a.start(2), start + a.end(2), a.group(1)))
    data = [n for n in ins if not re.search(r"(?i)clk|clock|rst|reset", n)]
    if not sites or not data:
        return None
    s, e, var = rng.choice(sites)
    sig = rng.choice(data)
    return _apply(text, s, e, sig), f"changed the reset value of '{var}' from a constant to the input '{sig}'"


def t_stmt_before_if(text, masked, rng):
    sites = []
    for b in _async_blocks(masked):
        m = re.match(r"\s*begin\b", masked[b.end():])
        if not m:
            continue
        pos = b.end() + m.end()
        if not re.match(r"\s*if\b", masked[pos:]):
            continue
        a = _nb_assigns(masked[pos:pos + 4000])
        if a:
            sites.append((pos, a[-1].group(1)))
    if not sites:
        return None
    pos, var = rng.choice(sites)
    return _apply(text, pos, pos, f"\n    {var} <= {var};"), f"inserted '{var} <= {var};' before the reset 'if'"


def t_second_driver(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if not b.group(3).strip()]
    targets = sorted({m.group(1) for m in _nb_assigns(masked)})
    end = masked.rfind("endmodule")
    if not blocks or not targets or end < 0:
        return None
    b = rng.choice(blocks)
    var = rng.choice(targets)
    block = f"\n  always @({b.group(1)} {b.group(2)}) {var} <= {var};\n"
    return _apply(text, end, end, block), f"added a second always block that drives '{var}'"


def t_blocking_in_nb(text, masked, rng):
    sites = _nb_assigns(masked)
    counts = {}
    for m in sites:
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    multi = [m for m in sites if counts[m.group(1)] >= 2]
    if not multi:
        return None
    m = rng.choice(multi)
    op = masked.index("<=", m.start())
    return _apply(text, op, op + 2, "="), f"changed one of the nonblocking assignments to '{m.group(1)}' to blocking"


def t_loop_condition(text, masked, rng):
    sites = list(re.finditer(rf"\bfor\s*\(\s*({ID})\s*=\s*[^;]+;\s*([^;]+);", masked))
    if not sites:
        return None
    m = rng.choice(sites)
    return (_apply(text, m.start(2), m.end(2), f"{m.group(1)} >= 0"),
            f"changed the condition of a 'for' loop on '{m.group(1)}' to '{m.group(1)} >= 0'")


def t_loop_no_step(text, masked, rng):
    sites = list(re.finditer(rf"\bfor\s*\(\s*({ID})\s*=\s*[^;]+;[^;]+;\s*([^)]+)\)", masked))
    if not sites:
        return None
    m = rng.choice(sites)
    return (_apply(text, m.start(2), m.end(2), f"{m.group(1)} = {m.group(1)}"),
            f"removed the step of a 'for' loop on '{m.group(1)}'")


def _instances(masked):
    modules = set(re.findall(rf"^\s*module\s+({ID})", masked, re.M))
    out = []
    for m in re.finditer(rf"^\s*({ID})\s*(#\s*\((?:[^()]|\([^()]*\))*\)\s*)?({ID})\s*\(", masked, re.M):
        if m.group(1) in modules:
            out.append(m)
    return out


def t_unknown_port(text, masked, rng):
    sites = []
    for m in _instances(masked):
        depth, j = 1, m.end()
        while j < len(masked) and depth:
            depth += {"(": 1, ")": -1}.get(masked[j], 0)
            j += 1
        for p in re.finditer(rf"\.({ID})\s*\(", masked[m.end():j]):
            sites.append((m.end() + p.start(1), m.end() + p.end(1), p.group(1)))
    if not sites:
        return None
    s, e, port = rng.choice(sites)
    return _apply(text, s, e, port + "_in"), f"renamed the port connection '.{port}' to '.{port}_in'"


def t_unknown_parameter(text, masked, rng):
    sites = _instances(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    if m.group(2):
        p = re.search(rf"\.({ID})\s*\(", m.group(2))
        if not p:
            return None
        s = m.start(2) + p.start(1)
        return _apply(text, s, s + len(p.group(1)), p.group(1) + "_W"), f"renamed the parameter '.{p.group(1)}' of an instance"
    pos = m.end(1)
    return _apply(text, pos, pos, " #(.WIDTH_JEV(8))"), f"added the unknown parameter WIDTH_JEV to an instance of {m.group(1)}"


def t_missing_module(text, masked, rng):
    sites = _instances(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    return (_apply(text, m.start(1), m.end(1), m.group(1) + "_v2"),
            f"changed the module name of an instance from {m.group(1)} to {m.group(1)}_v2")


TEMPLATES = {
    "illegal_code": [t_drop_semicolon, t_misspell_rhs],
    "unsupported_construct": [t_integer_to_real, t_reg_to_time],
    "timing_control": [t_wait, t_fork_join],
    "simulation_statement": [t_random, t_force],
    "event_list": [t_both_edges, t_edge_level],
    "async_reset": [t_reset_to_data, t_stmt_before_if],
    "multiple_drivers": [t_second_driver],
    "mixed_assignments": [t_blocking_in_nb],
    "unbounded_loop": [t_loop_condition, t_loop_no_step],
    "instance_mismatch": [t_unknown_port, t_unknown_parameter, t_missing_module],
}


# ---------------------------------------------------------------- trap templates (DC accepts)

def trap_nb_delay(text, masked, rng):
    sites = _nb_assigns(masked)
    if not sites:
        return None
    m = rng.choice(sites)
    return _apply(text, m.start(2), m.start(2), "#1 "), f"added the delay '#1' to '{m.group(1)} <='"


def trap_initial(text, masked, rng):
    targets = sorted({m.group(1) for m in _nb_assigns(masked)})
    end = masked.rfind("endmodule")
    if not targets or end < 0:
        return None
    var = rng.choice(targets)
    return _apply(text, end, end, f"\n  initial {var} = 0;\n"), f"added 'initial {var} = 0;'"


def trap_display(text, masked, rng):
    blocks = [b for b in _clocked_blocks(masked) if re.match(r"\s*begin\b", masked[b.end():])]
    targets = sorted({m.group(1) for m in _nb_assigns(masked)})
    if not blocks or not targets:
        return None
    b = rng.choice(blocks)
    pos = b.end() + re.match(r"\s*begin\b", masked[b.end():]).end()
    var = rng.choice(targets)
    return _apply(text, pos, pos, f'\n    $display("{var} = %0d", {var});'), f"added a $display of '{var}'"


# Each trap template has a twin template of the same kind of edit that DC rejects.
TRAP_TEMPLATES = {
    "nb_delay": (trap_nb_delay, ("timing_control", t_wait)),
    "initial": (trap_initial, ("simulation_statement", t_force)),
    "display": (trap_display, ("simulation_statement", t_random)),
}


def mutate(design_text, cls, seed, template_index=None):
    """Apply one template of class cls to design_text. Return (text, template name, description),
    or None if no template of the class finds a place."""
    rng = random.Random(seed)
    masked = blank_comments(design_text)
    templates = list(TEMPLATES[cls])
    if template_index is not None:
        templates = [templates[template_index % len(templates)]]
    rng.shuffle(templates)
    for t in templates:
        out = t(design_text, masked, rng)
        if out:
            return out[0], t.__name__, out[1]
    return None
