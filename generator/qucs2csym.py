#!/usr/bin/env python3
"""Qucs-S library symbols -> circuitRF symbols (.csym).

  qucs2csym.py <lib.lib> <Component> <out.csym>
  qucs2csym.py --kit <kitdir> [libs...]     every kit cell that has a Qucs-S
                                             component of the same name gets its
                                             symbol (default: the PDK's user_lib)

Qucs-S draws on a 10-unit grid with y down; circuitRF symbols use a 100-unit
grid, also y down, so every coordinate is scaled by 10. A <.PortSym x y n>
becomes pin n, named after the component's SPICE subcircuit port n (the port
list after 'gnd'), which is the PDK's own terminal order.
"""
import glob, json, math, os, re, sys

S = 10                                           # Qucs units -> circuitRF units


def components(path):
    text = open(path, encoding='latin-1').read()
    for m in re.finditer(r'<Component\s+(\S+?)>(.*?)</Component>', text, re.S):
        yield m.group(1), m.group(2)


def ports(body):
    """Port names from the SPICE subckt line: .SUBCKT name gnd p1 p2 ... key=val."""
    m = re.search(r'\.SUBCKT\s+\S+\s+(.*)', body, re.I)
    names = [t for t in m.group(1).split() if '=' not in t] if m else []
    return names[1:] if names and names[0].lower() == 'gnd' else names


def stroke(w):
    return 'Thin' if float(w) < 2 else 'Normal'


def convert(body):
    sym = re.search(r'<Symbol>(.*?)</Symbol>', body, re.S).group(1)
    names, prims, pins = ports(body), [], []
    L = lambda x1, y1, x2, y2, w: {"$type": "Line", "ColorRole": "SymbolLine", "StrokeTier": stroke(w),
                                   "X1": x1 * S, "Y1": y1 * S, "X2": x2 * S, "Y2": y2 * S}
    for line in sym.splitlines():
        t = re.findall(r'"[^"]*"|\S+', line.strip().strip('<>'))
        if not t:
            continue
        k, v = t[0], t[1:]
        num = lambda i: float(v[i])
        if k == 'Line':                          # x y dx dy color width style
            prims.append(L(num(0), num(1), num(0) + num(2), num(1) + num(3), v[5]))
        elif k == 'Arrow':                       # x y dx dy headlen headangle color width style
            x, y, dx, dy, hl, ha = (num(i) for i in range(6))
            prims.append(L(x, y, x + dx, y + dy, v[7]))
            a = math.atan2(dy, dx)
            for s in (1, -1):
                b = a + math.pi - s * math.radians(ha)
                prims.append(L(x + dx, y + dy, x + dx + hl * math.cos(b), y + dy + hl * math.sin(b), v[7]))
        elif k in ('Rectangle', 'Ellipse'):      # x y w h color width style [brush...]
            x, y, w, h = (num(i) for i in range(4))
            filled = len(v) > 9 and v[9] == '1'
            if k == 'Rectangle':
                prims.append({"$type": "Rect", "ColorRole": "SymbolLine", "StrokeTier": stroke(v[5]),
                              "Filled": filled, "Cx": (x + w / 2) * S, "Cy": (y + h / 2) * S, "W": w * S, "H": h * S})
            else:
                prims.append({"$type": "Ellipse", "ColorRole": "SymbolLine", "StrokeTier": stroke(v[5]),
                              "Filled": filled, "Cx": (x + w / 2) * S, "Cy": (y + h / 2) * S,
                              "Rx": w / 2 * S, "Ry": h / 2 * S})
        elif k == 'Text':                        # x y size color angle "text"
            prims.append({"$type": "Text", "Content": v[4].strip('"').replace('\\n', '\n'),
                          "AnchorX": num(0) * S, "AnchorY": num(1) * S, "FontSize": max(10, num(2) * 1.6),
                          "FontStyle": "Regular", "Align": "Left", "VAlign": "Top", "Rotation": "R0",
                          "ForceReadable": True, "ColorRole": "SymbolLine"})
        elif k == '.PortSym':                    # x y n [rotation]
            n = int(v[2])
            pins.append({"LocalX": round(num(0)) * S, "LocalY": round(num(1)) * S, "PortIndex": n - 1,
                         "Name": names[n - 1] if n - 1 < len(names) else str(n)})
    pins.sort(key=lambda p: p['PortIndex'])
    return {"FormatVersion": 6, "GridSize": 100, "PortCount": len(pins), "Primitives": prims, "Pins": pins}


def main():
    a = sys.argv[1:]
    if a and a[0] == '--kit':
        kit = a[1]
        libs = a[2:] or glob.glob(os.path.join(os.environ['PDKPATH'], 'libs.tech/qucs-s/user_lib/*.lib'))
        found = {name: body for lib in libs for name, body in components(lib)}
        for cell in sorted(os.listdir(kit)):
            ccell = os.path.join(kit, cell, '.ccell')
            if not os.path.exists(ccell) or cell not in found:
                continue
            sym = convert(found[cell])
            terms = [t['Name'] for t in json.load(open(ccell))['Terminals']]
            got = [p['Name'] for p in sym['Pins']]
            if len(got) != len(terms):           # never ship a symbol whose pins do not match
                print(f'{cell}: Qucs symbol has {got}, cell has {terms}; kept the old symbol')
                continue
            for p, t in zip(sym['Pins'], terms):  # same PDK order; use the cell's terminal names
                p['Name'] = t
            json.dump(sym, open(os.path.join(kit, cell, 'symbol', cell + '.csym'), 'w'), indent=1)
            print(f'{cell}: Qucs-S symbol, pins {terms}')
    elif len(a) == 3:
        found = dict(components(a[0]))
        json.dump(convert(found[a[1]]), open(a[2], 'w'), indent=1)
        print(a[2])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
