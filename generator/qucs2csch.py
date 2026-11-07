#!/usr/bin/env python3
"""Qucs-S schematic -> circuitRF schematic (.csch), for the PDK's symbol gallery.

  qucs2csch.py <in.sch> <out.csch> --kit <kitdir>

Every <Lib> component whose component name is a kit cell becomes an instance of
ws://IHP_SG13G2/<name> (the alias in the workspace's .cws) at the Qucs position (x10, y down, as qucs2csym.py), with its
Qucs properties (in the order of the component's .ID line in ../user_lib/*.lib)
mapped onto the cell's parameters. Qucs mirrors first (y -> -y), then turns n
times by (x, y) -> (y, -x); circuitRF negates x first, then turns R90 (x, y) ->
(-y, x). So a Qucs (mirror m, rotate n) is MirrorX m with R((180 m - 90 n) mod 360).

Every component of the gallery is listed in a table beside it, with its status
and note from qucs_cells.json (beside this script) when that file exists.
"""
import glob, json, os, re, sys
from qucs2csym import components, S

ALIAS = {'El': ('le', 1e-6)}                     # Qucs El is in um, the cell's le in m


def scaled(v, k):
    try:
        return f'{float(v) * k:g}'
    except ValueError:
        return f'({v})*{k:g}'


def convert(sch, kit):
    libdir = os.path.join(os.path.dirname(sch), '..', 'user_lib')
    props = {n: re.findall(r'"\d=([^="]+)=', re.search(r'<\.ID [^>]*>|$', b).group(0))
             for lib in glob.glob(os.path.join(libdir, '*.lib')) for n, b in components(lib)}
    comps, seen, xs, ys = [], [], [], []
    text = open(sch, encoding='latin-1').read()
    for line in re.search(r'<Components>(.*?)</Components>', text, re.S).group(1).splitlines():
        t = [s.strip('"') for s in re.findall(r'"[^"]*"|[^\s<>]+', line)]
        if not t:
            continue
        if t[0] != 'Lib':
            print(f'skipped {t[0]} {t[1]}: not a library component')
            continue
        name, x, y, m, n, cell, vals = t[1], int(t[3]) * S, int(t[4]) * S, int(t[7]), int(t[8]), t[11], t[13::2]
        seen.append(cell)
        xs.append(x), ys.append(y)
        ccell = os.path.join(kit, cell, '.ccell')
        if not os.path.exists(ccell):
            continue
        q = {ALIAS.get(k, (k, 1))[0]: (scaled(v, ALIAS[k][1]) if k in ALIAS else v, s == '1')
             for k, v, s in zip(props.get(cell, []), vals, t[14::2])}
        params = [{"Name": p['Name'], "Expression": q.get(p['Name'], (p['DefaultExpression'],))[0],
                   "Unit": p['Unit'], "ShowOnSchematic": q.get(p['Name'], (0, False))[1],
                   "Dimension": p['Dimension']} for p in json.load(open(ccell))['Parameters']]
        comps.append({"InstanceName": name, "Symbol": "Generic", "X": x, "Y": y,
                      "Rotation": f'R{(180 * m - 90 * n) % 360}', "MirrorX": bool(m), "Disable": "None",
                      "Parameters": params, "CellRef": f'ws://IHP_SG13G2/{cell}'})

    status = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qucs_cells.json')
    status = json.load(open(status)) if os.path.exists(status) else {}
    rows = []
    for c in sorted(set(seen)):
        inkit = os.path.exists(os.path.join(kit, c, '.ccell'))
        s = status.get(c, {"works": "yes" if inkit else "no", "note": "in the kit" if inkit else "not in the kit"})
        rows.append((c, s['works'], ' '.join(s.get('note', '').split())))
    rows.sort(key=lambda r: ({'yes': 0, 'partial': 1}.get(r[1], 2), r[0]))
    fs, x0, y0 = 150, max(xs) + 1500, min(ys) - 300
    cols = list(zip(('component', 'works', 'note'), *rows))
    objs = []
    for i, col in enumerate(cols):
        x = x0 + sum(max(map(len, c)) * fs * 0.58 + 2 * fs for c in cols[:i])
        for txt, y, style in ((col[0], y0, 'Bold'), ('\n'.join(col[1:]), y0 + 1.5 * fs, 'Regular')):
            objs.append({"Kind": "Text", "X": x, "Y": y, "Text": txt, "FontSize": fs, "FontStyle": style,
                         "Align": "Left", "VAlign": "Top", "ColorRole": "SymbolText"})
    return {"FormatVersion": 2, "GridSize": 100,
            "GridSnap": True, "AuthorGridDivisor": 20, "Components": comps, "Wires": [], "NetLabels": [],
            "Dots": [], "CanvasObjects": objs, "View": {"PanX": 0, "PanY": 0, "Zoom": 1}, "Analyses": []}


def main():
    a = sys.argv[1:]
    if len(a) != 4 or a[2] != '--kit':
        sys.exit(__doc__)
    csch = convert(a[0], a[3])
    csch = {"CellName": os.path.splitext(os.path.basename(a[1]))[0], **csch}
    json.dump(csch, open(a[1], 'w'), indent=1)
    print(f"{a[1]}: {len(csch['Components'])} kit cells placed")


if __name__ == '__main__':
    main()
