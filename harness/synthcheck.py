"""Decide from a DC log if a design synthesizes, and the reason if it does not.

The rules come from notes/synth_yesno.md and notes/synth_reason.md. The class table comes from the
DC probes of 2026-10-09 (probes/synth_classes_results.csv).
"""
import re

MSG_RE = re.compile(r"^(Error|Warning):.*\(([A-Z]+-\d+)\)\s*$")

# Errors that DC gives only after an earlier error. They do not show a class.
FOLLOW_ON_ERRORS = {
    "LBR-0",     # Cannot find the design 'top' in the library 'WORK'
    "UID-109",   # Can't find design 'top'
    "UID-4",     # Current design is not defined
    "VER-518",   # Cannot recover from previous errors
    "VER-40",    # Too many errors; can't continue
    # MV's flow continues its script after a failed design. The report commands then give this
    # error (seen in the real flow logs of 2026-10-09):
    "UID-22",    # No files or designs were specified
}

# Errors of the constraint commands of MV's flow. They come from an empty port list, not from the
# design: after a failed design, or for a design with no input port or no output port
# (set_input_delay ... [all_inputs] gives "Value for list 'port_pin_list' must have 1 elements").
# They never decide the result.
CONSTRAINT_ERRORS = {
    "CMD-036",   # Value for list '...' must have 1 elements
}

# Warnings that make a netlist incomplete. The design then does not synthesize.
INCOMPLETE_WARNINGS = {
    "LINK-5",    # Unable to resolve reference (a black box)
    "UID-341",   # The design has unresolved references
    "TRANS-4",   # No library cell for a register (**FFGEN**)
}

# The 10 classes of synth_reason, with the DC message IDs of each class. VER-294 is in two
# classes: the vlog result decides (see classify).
CLASS_IDS = {
    "illegal_code": {"VER-294", "VER-956", "VER-260", "VER-952",
                     "VER-913"},   # an undefined macro (seen in old REvolution candidates)
    "unsupported_construct": {"VER-294", "VER-177", "VER-191", "VER-700", "VER-183", "VER-186"},
    "timing_control": {"VER-188", "VER-187", "VER-193"},
    "simulation_statement": {"VER-967", "VER-968", "VER-966", "VER-969", "ELAB-939"},
    "event_list": {"ELAB-93", "ELAB-91", "ELAB-407"},
    "async_reset": {"ELAB-302", "TRANS-4"},
    "multiple_drivers": {"ELAB-366"},
    "mixed_assignments": {"VER-134"},
    "unbounded_loop": {"ELAB-900", "ELAB-901"},
    "instance_mismatch": {"LINK-1", "VER-216", "LINK-5", "UID-341"},
}
CLASSES = list(CLASS_IDS)


def dc_messages(log_text):
    """Return (error IDs, warning IDs) of a DC log as two sets."""
    errors, warnings = set(), set()
    for line in log_text.splitlines():
        m = MSG_RE.match(line.strip())
        if not m:
            continue
        (errors if m.group(1) == "Error" else warnings).add(m.group(2))
    return errors, warnings


def classify(log_text, vlog_ok, netlist_exists):
    """Classify one DC run.

    log_text        the DC log (synth.log of step 2)
    vlog_ok         True if QuestaSim vlog compiles the RTL with no error
    netlist_exists  True if step 2 wrote the netlist

    Return a dict:
        synthesizes  True only if all four conditions of synth_yesno.md are true (the errors
                     in CONSTRAINT_ERRORS do not count)
        classes      the synth_reason classes that the messages show (a sorted list)
        reason       the class if exactly one class shows, else None
        errors, warnings, unknown_errors
    """
    errors, warnings = dc_messages(log_text)
    if "SEC-50" in errors:
        raise ValueError("the log shows SEC-50 (no license): this run is not a result")
    design_errors = errors - CONSTRAINT_ERRORS
    real_errors = design_errors - FOLLOW_ON_ERRORS
    incomplete = warnings & INCOMPLETE_WARNINGS
    synthesizes = (not design_errors) and (not incomplete) and bool(netlist_exists)

    classes = set()
    # With an error, only the errors show the class. A failed module can also cause the
    # warning LINK-5 at the top, and that warning then does not show a second class.
    signals = real_errors if real_errors else incomplete
    for cls, ids in CLASS_IDS.items():
        hit = signals & ids
        if not hit:
            continue
        if hit == {"VER-294"}:
            # DC gives VER-294 ("Syntax error") also for legal SystemVerilog that it does not
            # support. If vlog also fails, the code is illegal. If vlog passes, it is legal.
            if cls == "illegal_code" and vlog_ok:
                continue
            if cls == "unsupported_construct" and not vlog_ok:
                continue
        classes.add(cls)
    known = set().union(*CLASS_IDS.values())
    unknown = sorted(real_errors - known)
    reason = None
    if not synthesizes and len(classes) == 1 and not unknown:
        reason = next(iter(classes))
    return {
        "synthesizes": synthesizes,
        "classes": sorted(classes),
        "reason": reason,
        "errors": sorted(errors),
        "warnings": sorted(warnings),
        "unknown_errors": unknown,
    }
