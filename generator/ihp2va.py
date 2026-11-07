#!/usr/bin/env python3
"""
Convert an IHP SG13G2 ngspice .lib device subckt into:
  * a Verilog-A parameter file that circuitRF's VerilogA component reads
    via  Load Parameters...  (docs/user/src/reference/veriloga.md)
  * a note of the subckt's external parasitics, which circuitRF cannot
    absorb into the compact model and you must draw as components.

The IHP cards carry expressions in terms of the device geometry multiplier
Nx and the corner multipliers (vbic_cje, vbic_is, ...) that cornerHBT.lib
sets.  Those are resolved to plain numbers here, because a Verilog-A
parameter declaration holds a literal.

Usage:
  ihp2va.py <models.lib> <subckt> [--nx N] [--corner typ|...] [-o out.va]
"""
import argparse, math, re, sys

DROP = {"level", "vbe_max", "vbc_max", "vce_max"}   # ngspice-only, not VBIC params


def read_lib(path):
    with open(path, "rb") as fh:                     # the IHP libs are ISO-8859-1
        return fh.read().decode("iso-8859-1")


def corner_params(text, corner):
    """Multipliers from cornerHBT.lib's .LIB <corner> block, e.g. vbic_cje=1.0."""
    out, inblock = {}, False
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith(".lib "):
            inblock = low.split()[1] == corner.lower()
            continue
        if low.startswith(".endl"):
            inblock = False
            continue
        if inblock and low.startswith(".param"):
            for k, v in re.findall(r"(\w+)\s*=\s*([-\w.+']+)", s[6:]):
                try:
                    out[k] = float(v.strip("'"))
                except ValueError:
                    pass
    return out


def subckt_block(text, name):
    """The lines of .subckt <name> ... .ends, with continuations joined."""
    lines, grab, buf = text.splitlines(), False, []
    for line in lines:
        s = line.strip()
        low = s.lower()
        if low.startswith(".subckt"):
            grab = low.split()[1] == name.lower()
            if grab:
                buf.append(s)
            continue
        if grab:
            if low.startswith(".ends"):
                break
            buf.append(s)
    if not buf:
        sys.exit(f"error: .subckt {name} not found in the library")
    # join '+' continuations onto the previous logical line
    joined = []
    for s in buf:
        if s.startswith("+") and joined:
            joined[-1] += " " + s[1:].strip()
        else:
            joined.append(s)
    return joined


def local_params(block):
    """.param defaults declared by the subckt itself (Nx, le, we, ...)."""
    out = {}
    for s in block:
        if s.lower().startswith(".param"):
            for k, v in re.findall(r"(\w+)\s*=\s*('[^']*'|\S+)", s[6:]):
                out[k] = v.strip("'")
    return out


def evaluate(expr, scope):
    """Evaluate a SPICE parameter expression to a float. ** is power in both."""
    e = expr.strip().strip("'")
    try:
        return float(e)
    except ValueError:
        pass
    env = {"__builtins__": {}}
    env.update({k: v for k, v in scope.items() if isinstance(v, (int, float))})
    env.update(exp=math.exp, log=math.log, sqrt=math.sqrt, pow=pow, abs=abs)
    try:
        return float(eval(e, env))          # noqa: S307 - fixed vocabulary above
    except Exception as exc:
        raise ValueError(f"cannot evaluate {expr!r}: {exc}") from exc


def model_card(block):
    """The .model line's parameters, as an ordered name -> expression map."""
    for s in block:
        if s.lower().startswith(".model"):
            body = s.split(None, 3)
            rest = body[3] if len(body) > 3 else ""
            return dict(re.findall(r"(\w+)\s*=\s*('[^']*'|\S+)", rest))
    sys.exit("error: no .model card inside that subckt")


def parasitics(block, scope):
    """R/C/L lines in the subckt — these stay outside the compact model."""
    out = []
    for s in block:
        if re.match(r"^[RCL]\w*\s", s, re.I):
            bits = s.split()
            m = re.search(r"\b[RCL]\s*=\s*('[^']*'|\S+)", s, re.I)
            if m:
                try:
                    out.append((bits[0], bits[1], bits[2], evaluate(m.group(1), scope)))
                except ValueError:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lib"); ap.add_argument("subckt")
    ap.add_argument("--nx", type=float, default=None,
                    help="emitter multiplicity (default: the subckt's own)")
    ap.add_argument("--corner", default="hbt_typ")
    ap.add_argument("--temp", type=float, default=27.0,
                    help="temperature in C that the cards' temper resolves to")
    ap.add_argument("--cornerlib", default=None)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    text = read_lib(a.lib)
    block = subckt_block(text, a.subckt)

    # ngspice exposes the simulation temperature as temper/temp; the IHP cards
    # bake a temperature factor into tf through it, so it must have a value.
    scope = {"temper": a.temp, "temp": a.temp}
    if a.cornerlib:
        scope.update(corner_params(read_lib(a.cornerlib), a.corner))
    for k, v in local_params(block).items():
        try:
            scope[k] = evaluate(v, scope)
        except ValueError:
            pass
    if a.nx is not None:
        scope["Nx"] = a.nx

    card, lines, skipped = model_card(block), [], []
    for name, expr in card.items():
        if name.lower() in DROP:
            skipped.append(f"{name} = {expr}")
            continue
        try:
            lines.append((name, evaluate(expr, scope), expr))
        except ValueError as exc:
            skipped.append(f"{name} = {expr}   ({exc})")

    w = max(len(n) for n, _, _ in lines)
    body = [f"// {a.subckt} from {a.lib.split('/')[-1]}",
            f"// corner={a.corner}  Nx={scope.get('Nx')}  temper={a.temp} C",
            "// Load with: VerilogA component -> Load Parameters...", ""]
    for name, val, expr in lines:
        note = f"   // {expr}" if expr.strip().strip("'") != f"{val}" else ""
        body.append(f"parameter real {name:<{w}} = {val:.6g};{note}")

    para = parasitics(block, scope)
    if para:
        body += ["", "// --- NOT model parameters: draw these as components ---"]
        for ref, n1, n2, val in para:
            body.append(f"//   {ref}  {n1}-{n2}  = {val:.6g}")
    if skipped:
        body += ["", "// --- not emitted (ngspice-only / unevaluated) ---"]
        body += [f"//   {s}" for s in skipped]

    out = "\n".join(body) + "\n"
    if a.out:
        open(a.out, "w").write(out)
        print(f"wrote {a.out}: {len(lines)} parameters, {len(para)} parasitics, "
              f"{len(skipped)} skipped")
    else:
        print(out)


if __name__ == "__main__":
    main()
