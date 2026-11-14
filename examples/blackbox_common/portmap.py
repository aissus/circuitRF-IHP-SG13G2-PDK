#!/usr/bin/env python3
"""portmap.py <setup.cem>...: writes PORTS.md in this folder, what each port of each setup's EM result is, read
from circuitRF's own outputs:

  the Touchstone header      port k's label, layer, position and calibration ('! circuitRF-EM port k: ...')
  explain --component-ports  each cut pin's class and what its port returns through; the run's return plane
  <setup>_cosim.cnl          which co-simulation node each port is, and which model terminal sits on it
  the cell's schematic       the net: `circuitrf netlist` of the cell the layout belongs to, reached through the
                             layout's SchematicId links (a drawn label to its Term, an instance to its part)

Run in an example's folder, inside the image (it calls circuitrf), e.g.
    python3 ../blackbox_common/portmap.py PAIR/em/pair_B.cem PAIR/em/pair_A.cem
"""
import glob, json, os, re, subprocess, sys
TRUST = ['--trust-kit', 'ihp-sg13g2-pcells']


def crf(*args):
    return subprocess.run(['circuitrf', *args, *TRUST], capture_output=True, text=True).stdout


def schematic_nets(cell):
    """{('P', '1'): net} for the Terms, {(inst, PIN): net} for the parts, from the cell's extracted netlist."""
    text = crf('netlist', f'{cell}/schematic/{cell}.csch')
    pins = {m[0]: m[1].split() for m in re.findall(r'^define (\S+) \(([^)]*)\)', text, re.M)}
    nets = {}
    for typ, inst, nodes in re.findall(r'^(\w+):(\w+)\s+(.*)$', text, re.M):
        nodes = [n for n in nodes.split() if '=' not in n]
        if typ == 'Port':
            nets[('P', inst[1:])] = nodes[0]
        for pin, node in zip(pins.get(typ, []), nodes):
            nets[(inst, pin.upper())] = node
    return nets


def layout(cell):
    """Drawn labels' schematic links, and each instance's pin positions (from its generated cell)."""
    d = json.load(open(f'{cell}/layout/{cell}.clay'))
    links = {s['Text']: s.get('SchematicId') for s in d['Shapes'] if s.get('IsPort')}
    pinpos = []
    for i in d['Instances']:
        g = json.load(open(glob.glob(os.path.join(cell, 'layout', i['CellRef'], 'layout', '*.clay'))[0]))
        pinpos += [(i['SchematicId'], p['Name'], (i['X'] + p['X']) / 1e3, (i['Y'] + p['Y']) / 1e3) for p in g['Pins']]
    return links, pinpos


def one(cem):
    cell, name = cem.split('/')[0], os.path.basename(cem)[:-4]
    snp = [p for p in glob.glob(f'results/{name}.s*p')]
    if not snp:
        return f'### {name}\n\nNo result yet: run `circuitrf em {cem}`.\n'
    snp = snp[0]
    head = [l.rstrip() for l in open(snp) if l.startswith('!')]
    rows = [l for l in open(snp) if l.strip() and not l.startswith(('!', '#'))]
    freqs = [float(l.split()[0]) for l in rows if not l.startswith(' ')]
    names = dict(re.findall(r'^! Port\[(\d+)\] = (.*)$', '\n'.join(head), re.M))
    info = {k: (lay, float(x), float(y), cal) for k, lay, x, y, cal in
            re.findall(r"^! circuitRF-EM port (\d+): '[^']*' on '([^']*)' at \(([-\d.]+), ([-\d.]+) um\), \w+, (\w+)",
                       '\n'.join(head), re.M)}
    ex = crf('explain', cem, '--component-ports')
    plane = re.search(r'return plane\s+(\S+)', ex).group(1)
    cut = {m[2]: (m[1], m[3].strip()) for m in
           re.findall(r"cut pin\s+(\S+): (\w+),.*port (\d+) '[^']*', returning through (.*)$", ex, re.M)}
    cos, model = {}, {}
    if os.path.exists(f'{name}_cosim.cnl'):
        t = open(f'{name}_cosim.cnl').read()
        board = re.search(r"^; BOARD's ports: (.*)$", t, re.M).group(1)
        cos = {v: k for k, v in re.findall(r'(p\d+) is ([^,.]+(?:\.[A-Za-z0-9]+)?)', board)}
        terms = {m[0]: m[1].split() for m in re.findall(r'^define (\S+) \(([^)]*)\)', t, re.M)}
        for typ, inst, nodes in re.findall(r'^(\w+):(\w+)\s+(.*)$', t, re.M):
            for pin, n in zip(terms.get(typ, []), nodes.split()):
                model.setdefault(n, f'{typ}:{inst} {pin}')
    nets = schematic_nets(cell)
    links, pinpos = layout(cell)
    tab = ['| Index | Name | Port | Net | Reference | Calibration | Co-sim node |', '|---|---|---|---|---|---|---|']
    ours = []
    for k in sorted(names, key=int):
        n, (lay, x, y, cal) = names[k], info[k]
        cal = 'uncalibrated' if cal == 'uncalibrated' else 'calibrated'
        if k in cut:                                    # a cut pin, by its path and pin name
            inst, pin = n.rsplit('.', 1)
            what, net = f'{n} (cut pin, {cut[k][0]})', nets.get((inst, pin))
            ref = 'ground (Backside)' if "run's ground" in cut[k][1] else cut[k][1]
        else:                                           # a drawn label
            sid = links.get(n)
            net = nets.get(('P', sid[1:])) if sid else None
            at = [(i, p) for i, p, px, py in pinpos if abs(px - x) < 0.01 and abs(py - y) <= 1.0]
            what = f"label '{n}'" + (f' ({sid})' if sid else '') + f' on {lay}'
            if net is None and at:                      # a label on an instance's pin face, with no Term of its own
                net, what = nets.get(at[0], at[0][1]), what + f" at {at[0][0]}.{at[0][1]}'s face"
            net = net or 'TopMetal1 plane (the tie; no schematic net)'
            ref = f'ground ({plane})'
        node = cos.get(n, '')
        node = f'{node} ({model[node]})' if node in model else node
        tab.append(f'| {k} | P{int(k):02d} | {what} | {net} | {ref} | {cal} | {node} |')
        short = 'plane' if net.startswith('TopMetal1 plane') else net
        ours.append(f'! Port {k} = P{int(k):02d}  {n:<9} net={short:<6} ref=ground  {cal}')
    ours.append(f'! DC: none, the lowest row is {min(freqs):g} GHz')
    return '\n'.join([f'### {name}', '', f'`{cem}` -> `{snp}`: {len(names)} ports, {len(freqs)} rows from '
                      f'{min(freqs):g} to {max(freqs):g} GHz, no 0 Hz row.', '', *tab, '',
                      'circuitRF writes:', '', '```', *[h for h in head if re.match(r'! (Port\[|circuitRF-EM port )', h)],
                      '```', '', 'The same, one line per port, as this example proposes:', '', '```', *ours, '```', ''])


if __name__ == '__main__':
    out = ['# Port map', '',
           'Generated by `portmap.py` from the EM results in `results/`. Rerun it after an EM run.', '',
           'Name is the port\'s index as P01, P02, ... Port is a drawn port label (with the schematic Term its '
           'SchematicId names) or a cut instance pin (path.pin, and its class from `explain --component-ports`). '
           'Net is the schematic net. Reference is what the port returns through. Co-sim node is the node of '
           '`<setup>_cosim.cnl` on that port, and the model terminal circuitRF put on it.', '']
    out += [one(c) for c in sys.argv[1:]]
    open('PORTS.md', 'w').write('\n'.join(out))
    print('wrote PORTS.md')
