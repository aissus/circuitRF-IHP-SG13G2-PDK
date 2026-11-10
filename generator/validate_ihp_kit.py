#!/usr/bin/env python3
"""Check the IHP SG13G2 circuitRF kit against the PDK's own models in ngspice.

    python3 validate_ihp_kit.py [--kit kit/IHP_SG13G2]

Each test places a kit cell in a schematic bench (the way the GUI does: a cell
reference into the library) and runs it with the circuitRF CLI; the same device
runs in ngspice from the PDK's model files. HBTs: Ic and Ib at two VBE, over
devices, Nx, le, corners and temperature. Resistors: R over w, l, b and
corners. MIM capacitor: C at 1 GHz. Small-signal noise (NF, NFmin, Rn, Sopt)
of the HBT and the NMOS against ngspice's .sp with noise, and an HBT Colpitts
oscillator against an ngspice transient; for the HBT, ngspice runs the same
compiled VBIC 1.3 with the kit cell's parameters. Exit code 1 if anything is
off by more than the tolerance.

The same DC, MIM and noise cases also run on the PDK's own parts as circuitRF
imports them (pdk://ihp-sg13g2/<part>, rows marked pdk://; the NMOS noise runs
only there), with the kit's VBIC 1.3 declared to stand in for the built-in VBIC
the PDK's HBT cards name.
"""
import argparse, cmath, json, math, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ihp2crf import Sheet, par

PDK = os.environ['PDKPATH']
CORNER_LIB = {'hbt': ('cornerHBT.lib', 'hbt'), 'res': ('cornerRES.lib', 'res'), 'cap': ('cornerCAP.lib', 'cap')}
CNAME = ('typ', 'bcs', 'wcs')
STAND_IN = {"model": "npn", "level": "9", "module": "vbic13_5t",
            "parameters": {"dtemp": "trise", "vbe_max": None, "vbc_max": None, "vce_max": None}}
# What circuitRF's import does not yet do, by row: reported as a gap, not a failure, while it is off.
GAPS = {'pdk:// sg13_lv_nmos w=1e-05 l=1.3e-07 ng=4 mos_tt  C':
        "the PDK picks a MOS's source/drain areas with .if on ng, which circuitRF's import settles once, at ng=1"}


def cell_pins(kit, cell):
    sym = json.load(open(f'{kit}/{cell}/symbol/{cell}.csym'))
    return {p['Name']: (p['LocalX'], p['LocalY']) for p in sym['Pins']}


def bench(ws, kit, cell, params, nets, analyses, extra=None):
    """A test-bench cell in workspace ws placing kit cell with params; nets: pin -> net."""
    name = 'B_' + re.sub(r'\W', '_', cell + '_' + '_'.join(f'{k}{v}' for k, v in params.items()))
    d = f'{ws}/{name}/schematic'
    os.makedirs(d, exist_ok=True)
    json.dump({"FormatVersion": 1, "Parameters": [], "IsTestBench": True, "Terminals": [], "NumPorts": 0},
              open(f'{ws}/{name}/.ccell', 'w'))
    s = Sheet(name)
    s.comps.append({"InstanceName": "X1", "Symbol": "Generic", "X": 0, "Y": 0, "Rotation": "R0",
                    "MirrorX": False, "Disable": "None",
                    "Parameters": [par(k, str(v), True) for k, v in params.items()],
                    "CellRef": os.path.relpath(f'{kit}/{cell}', d)})
    for pin, (x, y) in cell_pins(kit, cell).items():
        dx, dy = (100 if x > 0 else -100 if x < 0 else 0), (100 if y > 0 else -100 if y < 0 else 0)
        s.stub(x, y, dx, dy, nets[pin])
    if extra:
        extra(s)
    s.write(f'{d}/{name}.csch')
    doc = json.load(open(f'{d}/{name}.csch'))
    doc['Analyses'] = analyses
    json.dump(doc, open(f'{d}/{name}.csch', 'w'), indent=1)
    return f'{d}/{name}.csch'


def vsource(s, x, net, volts, probe):
    """Vdc from ground to net through an IProbe named probe (current into the DUT)."""
    s.comp('V' + probe, 'Vdc', x, 2000, [par('Vdc', str(volts), True)])
    s.stub(x, 2200, 0, 100, '0')
    s.stub(x, 1800, 0, -100, 's_' + probe)
    s.comp(probe, 'IProbe', x + 400, 1500, [])       # pins np (0,100) nm (100,100)
    s.stub(x + 400, 1600, 0, 100, 's_' + probe)
    s.stub(x + 500, 1600, 0, 100, net)


def crf(verb, path, *args):
    r = subprocess.run(['circuitrf', verb, path, *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stdout[-600:] + r.stderr[-600:])
    return r.stdout


def currents(out):
    return {m[0]: float(m[1]) for m in re.findall(r'^\s*(I\w+)\s+([-+0-9.eE]+)\s*$', out, re.M)}


def ngspice(lines):
    with tempfile.TemporaryDirectory() as t:
        open(f'{t}/n.cir', 'w').write('\n'.join(lines) + '\n.end\n')
        out = subprocess.run(['ngspice', '-b', f'{t}/n.cir'], capture_output=True, text=True, cwd=t).stdout
    return {m[0].lower(): complex(float(m[1]), float(m[2] or 0))
            for m in re.findall(r'^(\S+)\s*=\s*([-+0-9.eE]+)(?:,\s*([-+0-9.eE]+))?', out, re.M)}


def lib(kind, corner):
    f, p = CORNER_LIB[kind]
    return f'.lib {f} {p}_{CNAME[corner]}'


def check(label, got, ref, tol, rows, floor=0.0):
    err = abs(got - ref) / abs(ref)
    rows.append((label, got, ref, err, err <= tol or abs(got - ref) <= floor))


def caps_from_snp(path):
    """C at each port of a one-frequency Touchstone file whose ports are separate parts, from S_kk."""
    fmt = next(l for l in open(path) if l.startswith('#')).upper()
    v = [float(x) for l in open(path) if l.strip() and l[0] not in '!#' for x in l.split('!')[0].split()]
    n = round(math.sqrt((len(v) - 1) / 2))
    f = v[0] * {'HZ': 1, 'KHZ': 1e3, 'MHZ': 1e6, 'GHZ': 1e9}[fmt.split()[1]]
    caps = []
    for k in range(n):
        a, b = v[1 + 2 * (k * n + k)], v[2 + 2 * (k * n + k)]
        s = complex(a, b) if ' RI' in fmt else cmath.rect(10 ** (a / 20) if ' DB' in fmt else a, math.radians(b))
        caps.append(((1 - s) / (1 + s) / 50).imag / (2 * math.pi * f))
    return caps


def pdk_workspace(ws, kit):
    """A workspace on the PDK as circuitRF imports it. The PDK's HBT cards name ngspice's built-in
    VBIC (level 9); the kit's compiled VBIC 1.3 is declared to stand in for it."""
    json.dump({"FormatVersion": 2, "LibraryRefs": [], "KnownFiles": []}, open(f'{ws}/.cws', 'w'))
    crf('import', 'pdk', PDK, '--into', ws)
    cws = json.load(open(f'{ws}/.cws'))
    cws['PdkRefs'][0]['Settings']['standIns'] = [dict(STAND_IN, file=f'{kit}/models/osdi/vbic_1p3_5t.osdi')]
    json.dump(cws, open(f'{ws}/.cws', 'w'), indent=1)


def pdk_bench(ws, name, libs, insts, analysis, verb, *args):
    """The PDK's own parts (pdk://ihp-sg13g2/<part>) placed in one bench with the corners of the .lib
    lines `libs` selected, extracted, and wired. Each of insts is (part, parameters, nodes, lines):
    nodes are the extracted line's nodes in order (a substrate global after them goes to ground),
    lines the sources around it. One bench per corner and temperature: every extract and run loads
    the whole imported PDK, about 10 s."""
    os.makedirs(f'{ws}/{name}/schematic')
    json.dump({"FormatVersion": 1, "Parameters": [], "IsTestBench": True, "Terminals": [], "NumPorts": 0},
              open(f'{ws}/{name}/.ccell', 'w'))
    comps = [{"InstanceName": f"X{k}", "Symbol": "Generic", "X": 0, "Y": 400 * k, "Rotation": "R0",
              "MirrorX": False, "Disable": "None", "Parameters": [par(n, str(v), True) for n, v in p.items()],
              "CellRef": 'pdk://ihp-sg13g2/' + part} for k, (part, p, _, _) in enumerate(insts)]
    csch = f'{ws}/{name}/schematic/{name}.csch'
    json.dump({"FormatVersion": 2, "CellName": name, "GridSize": 100, "GridSnap": True, "AuthorGridDivisor": 20,
               "Components": comps, "Wires": [], "NetLabels": [], "Dots": [], "CanvasObjects": [],
               "View": {"PanX": 0, "PanY": 0, "Zoom": 1}, "Analyses": [],
               "CornerSelections": {'ihp-sg13g2|libs.tech/ngspice/models/' + l.split()[1]: l.split()[2] for l in libs}},
              open(csch, 'w'), indent=1)
    cnl = f'{ws}/{name}.cnl'
    crf('netlist', csch, '-o', cnl)
    s = open(cnl).read()
    for k, (_, _, nodes, lines) in enumerate(insts):
        m = re.search(rf'^(\S+:X{k})\s+(.*)$', s, re.M)
        tok = m.group(2).split()
        n = sum('=' not in t for t in tok)
        line = ' '.join([m.group(1)] + nodes + ['0'] * (n - len(nodes)) + [t for t in tok if '=' in t])
        s = s.replace(m.group(0), line + '\n' + '\n'.join(lines))
    open(cnl, 'w').write(s + '\n' + analysis + '\n')
    return crf(verb, cnl, *args)


def pdk_dc(ws, queue, rows):
    """The queued DC cases on the PDK's own parts, one bench per (corner, temperature). A case is
    (.lib line, part, parameters, nets, {net: volts}, [(label, net, reference, tol, floor, f)]):
    nets are the part's nodes in order; each source's probe gives the current into the part at that
    net, and f(current) is compared with the reference."""
    for (corner, temp), cases in queue.items():
        insts, todo = [], []
        for k, (libline, part, p, nets, volts, checks) in enumerate(cases):
            u = lambda n: n if n == '0' else f'{n}_{k}'
            insts.append((part, p, [u(n) for n in nets],
                          [f'Vdc:V{u(n)} s{u(n)} 0 Vdc={v} V\nIProbe:I{u(n)} s{u(n)} {u(n)}' for n, v in volts.items()]))
            todo += [(label, f'I{u(net)}', ref, tol, floor, f) for label, net, ref, tol, floor, f in checks]
        got = currents(pdk_bench(ws, f'P{corner}_{temp}', {c[0] for c in cases}, insts, 'analysis DC1 type=dc',
                                 'dc', '--set', f'temp={temp}'))
        for label, probe, ref, tol, floor, f in todo:
            check('pdk:// ' + label, f(got[probe]), ref, tol, rows, floor)


def run(kit, ws, pws):
    rows, queue = [], {}
    q = lambda corner, temp, *case: queue.setdefault((corner, temp), []).append(case)
    same = lambda i: i
    # ---- HBTs
    hbt_cases = [('npn13G2', {'Nx': 1}), ('npn13G2', {'Nx': 2}), ('npn13G2', {'Nx': 8}),
                 ('npn13G2l', {'Nx': 1}), ('npn13G2l', {'Nx': 4, 'le': 5e-6}),
                 ('npn13G2v', {'Nx': 1}), ('npn13G2v', {'Nx': 8}),
                 ('npn13G2', {'Nx': 2, 'corner': 1}), ('npn13G2', {'Nx': 2, 'corner': 2}),
                 ('npn13G2v', {'Nx': 8, 'corner': 2}),
                 ('npn13G2', {'Nx': 2, 'T': 85}), ('npn13G2', {'Nx': 2, 'selft': 0})]
    for cell, p in hbt_cases:
        for vbe in (0.80, 0.88):
            def ex(s, vbe=vbe):
                vsource(s, 1000, 'nb', vbe, 'IB'); vsource(s, 2000, 'nc', 1.5, 'IC')
            b = bench(ws, kit, cell, p, {'c': 'nc', 'b': 'nb', 'e': '0', 'bn': '0'},
                      [{"Type": "dc", "Name": "DC1", "Enabled": True}], ex)
            got = currents(crf('dc', b))
            corner, temp = p.get('corner', 0), p.get('T', 27)
            inst = ' '.join(f'{k}={v}' for k, v in p.items() if k not in ('corner', 'T'))
            ref = ngspice([f'* {cell}', lib('hbt', corner), f'.temp {temp}', f'VB b 0 {vbe}', 'VC c 0 1.5',
                           f'X1 c b 0 0 {cell} {inst}', '.control', 'op', 'print -i(VC)', 'print -i(VB)', '.endc'])
            tag = f'{cell} {inst} {CNAME[corner]} {temp}C VBE={vbe}'
            # 2 % or 10 nA: at sub-uA base currents with self-heating circuitRF's DC
            # differs from ngspice by a few nA (not the kit: the bare OSDI does the
            # same), and at high power the VBIC 1.3 source's temperature-dependent
            # rth differs from ngspice's built-in VBIC by up to ~1.5 %.
            check(tag + '  Ic', got['IC'], ref['-i(vc)'].real, 0.02, rows, 10e-9)
            check(tag + '  Ib', got['IB'], ref['-i(vb)'].real, 0.02, rows, 10e-9)
            q(corner, temp, lib('hbt', corner), cell, {k: v for k, v in p.items() if k not in ('corner', 'T')},
              ['nc', 'nb', '0', '0'], {'nb': vbe, 'nc': 1.5},
              [(tag + '  Ic', 'nc', ref['-i(vc)'].real, 0.02, 10e-9, same),
               (tag + '  Ib', 'nb', ref['-i(vb)'].real, 0.02, 10e-9, same)])
            if 'selft' in p:        # the compiled device keeps the PDK's selft=1
                continue
            # the same device compiled whole (harmonicaRF's DUT): only Nx (le), corner and temp
            ext = ' '.join(f'{k}={v}' for k, v in p.items() if k != 'T')
            open(f'{ws}/osdi.cnl', 'w').write(
                f'Vdc:VB sb 0 Vdc={vbe} V\nIProbe:IB sb nb\nVdc:VC sc 0 Vdc=1.5 V\nIProbe:IC sc nc\n'
                f'ExtDevice:DUT nb nc 0 Provider=VerilogA|{kit}/models/osdi/{cell}.osdi Type={cell} {ext} temp={temp}\n'
                'analysis DC1 type=dc\n')
            got = currents(crf('dc', f'{ws}/osdi.cnl'))
            check(tag + '  Ic .osdi', got['IC'], ref['-i(vc)'].real, 0.02, rows, 10e-9)
            check(tag + '  Ib .osdi', got['IB'], ref['-i(vb)'].real, 0.02, rows, 10e-9)
    # ---- resistors
    res_cases = [('rsil', {'w': 0.5e-6, 'l': 0.5e-6}), ('rsil', {'w': 2e-6, 'l': 20e-6}),
                 ('rsil', {'w': 2e-6, 'l': 20e-6, 'corner': 1}),
                 ('rppd', {'w': 0.5e-6, 'l': 0.5e-6}), ('rppd', {'w': 1e-6, 'l': 10e-6, 'b': 2}),
                 ('rppd', {'w': 1e-6, 'l': 10e-6, 'corner': 2}),
                 ('rhigh', {'w': 0.5e-6, 'l': 0.96e-6}), ('rhigh', {'w': 1e-6, 'l': 10e-6, 'b': 1}),
                 ('rhigh', {'w': 1e-6, 'l': 10e-6, 'corner': 1})]
    for cell, p in res_cases:
        b = bench(ws, kit, cell, p, {'1': 'n1', '2': '0', 'bn': '0'},
                  [{"Type": "dc", "Name": "DC1", "Enabled": True}],
                  lambda s: vsource(s, 1000, 'n1', 0.1, 'IR'))
        got = 0.1 / currents(crf('dc', b))['IR']
        corner = p.get('corner', 0)
        inst = ' '.join(f'{k}={v}' for k, v in p.items() if k != 'corner')
        ref = ngspice([f'* {cell}', lib('res', corner), 'V1 n1 0 0.1', f'X1 n1 0 0 {cell} {inst}',
                       '.control', 'op', 'print -i(V1)', '.endc'])
        check(f'{cell} {inst} {CNAME[corner]}  R', got, 0.1 / ref['-i(v1)'].real, 0.01, rows)
        q(corner, 27, lib('res', corner), cell, {k: v for k, v in p.items() if k != 'corner'}, ['n1', '0'],
          {'n1': 0.1}, [(f'{cell} {inst} {CNAME[corner]}  R', 'n1', 0.1 / ref['-i(v1)'].real, 0.01, 0, lambda i: 0.1 / i)])
    # ---- MOSFETs: Id in saturation and in triode
    mos_cases = [('sg13_lv_nmos', {'w': 1e-6, 'l': 0.13e-6, 'ng': 1}), ('sg13_lv_nmos', {'w': 10e-6, 'l': 0.13e-6, 'ng': 4}),
                 ('sg13_lv_nmos', {'w': 1e-6, 'l': 0.13e-6, 'ng': 1, 'corner': 1}),
                 ('sg13_lv_nmos', {'w': 1e-6, 'l': 0.13e-6, 'ng': 1, 'corner': 2}),
                 ('sg13_lv_pmos', {'w': 1e-6, 'l': 0.13e-6, 'ng': 1}), ('sg13_lv_pmos', {'w': 4e-6, 'l': 0.5e-6, 'ng': 2, 'corner': 2}),
                 ('sg13_hv_nmos', {'w': 1e-6, 'l': 0.45e-6, 'ng': 1}), ('sg13_hv_nmos', {'w': 4e-6, 'l': 0.45e-6, 'ng': 2, 'corner': 1}),
                 ('sg13_hv_pmos', {'w': 1e-6, 'l': 0.4e-6, 'ng': 1}), ('sg13_hv_pmos', {'w': 4e-6, 'l': 0.4e-6, 'ng': 2, 'corner': 2})]
    for cell, p in mos_cases:
        sg, vdd, fam = (-1 if 'pmos' in cell else 1), (1.2 if '_lv_' in cell else 3.3), cell[5:7]
        corner = p.get('corner', 0)
        inst = ' '.join(f'{k}={v}' for k, v in p.items() if k != 'corner')
        for vgs, vds in ((vdd / 2, vdd), (vdd, 0.1)):
            def ex(s, vgs=vgs, vds=vds):
                vsource(s, 1000, 'ng', sg * vgs, 'IG'); vsource(s, 2000, 'nd', sg * vds, 'ID')
            b = bench(ws, kit, cell, p, {'d': 'nd', 'g': 'ng', 's': '0', 'b': '0'},
                      [{"Type": "dc", "Name": "DC1", "Enabled": True}], ex)
            got = currents(crf('dc', b))['ID']
            ref = ngspice([f'* {cell}', f'.lib cornerMOS{fam}.lib mos_{("tt", "ff", "ss")[corner]}',
                           f'VG g 0 {sg * vgs}', f'VD d 0 {sg * vds}', f'X1 d g 0 0 {cell} {inst}',
                           '.control', 'op', 'print -i(VD)', '.endc'])
            check(f'{cell} {inst} {("tt", "ff", "ss")[corner]} VGS={vgs:g} VDS={vds:g}  Id', got,
                  ref['-i(vd)'].real, 0.01, rows, 1e-9)
            q(corner, 27, f'.lib cornerMOS{fam}.lib mos_{("tt", "ff", "ss")[corner]}', cell,
              {k: v for k, v in p.items() if k != 'corner'}, ['nd', 'ng', '0', '0'], {'ng': sg * vgs, 'nd': sg * vds},
              [(f'{cell} {inst} {("tt", "ff", "ss")[corner]} VGS={vgs:g} VDS={vds:g}  Id', 'nd',
                ref['-i(vd)'].real, 0.01, 1e-9, same)])
    # ---- C at 1 GHz from S11: the MIM capacitor, and the MOS drain (its junction and overlap
    # capacitance, from the subckt's geometry formulas, for odd and even ng)
    caps = [('cap_cmim', p, {'PLUS': 'n1', 'MINUS': '0'}, lib('cap', p.get('corner', 0)))
            for p in ({'w': 7e-6, 'l': 7e-6}, {'w': 20e-6, 'l': 30e-6}, {'w': 20e-6, 'l': 30e-6, 'corner': 2})]
    caps += [(c, p, {'d': 'n1', 'g': '0', 's': '0', 'b': '0'}, f'.lib cornerMOS{c[5:7]}.lib mos_tt')
             for c, p in (('sg13_lv_nmos', {'w': 10e-6, 'l': 0.13e-6, 'ng': 1}),
                          ('sg13_lv_nmos', {'w': 10e-6, 'l': 0.13e-6, 'ng': 4}),
                          ('sg13_hv_pmos', {'w': 10e-6, 'l': 0.4e-6, 'ng': 3}))]
    capq = {}
    for cell, p, nets, libline in caps:
        def ex(s):
            s.comp('P1', 'TermG', 1000, 2000, [par('Num', '1', True), par('Z', '50', True)])
            s.stub(1000, 1800, 0, -100, 'n1'); s.stub(1000, 2200, 0, 100, '0')
        b = bench(ws, kit, cell, p, nets,
                  [{"Type": "sp", "Name": "SP1", "Enabled": True,
                    "Sweeps": [{"StartExpr": "1", "StopExpr": "1", "NumPoints": 1, "Mode": "PointCount",
                                "Kind": "Linear", "StartUnit": "GHz", "StopUnit": "GHz"}]}], ex)
        with tempfile.TemporaryDirectory() as t:
            crf('sparam', b, '-o', f'{t}/c.s1p')
            got, = caps_from_snp(f'{t}/c.s1p')
        corner = p.get('corner', 0)
        inst = ' '.join(f'{k}={v}' for k, v in p.items() if k != 'corner')
        ref = ngspice([f'* {cell}', libline, 'V1 n1 0 dc 0 ac 1', f'X1 {" ".join(nets.values())} {cell} {inst}',
                       '.control', 'ac lin 1 1e9 1e9', 'print i(V1)', '.endc'])
        cref = -ref['i(v1)'].imag / (2 * math.pi * 1e9)
        check(f'{cell} {inst} {libline.split()[-1]}  C', got, cref, 0.01, rows)
        capq.setdefault(corner, []).append((libline, cell, {k: v for k, v in p.items() if k != 'corner'},
                                            list(nets.values()), f'{cell} {inst} {libline.split()[-1]}  C', cref))
    # the same cases on the PDK's own parts: DC, then C with a port on each part of a corner
    pdk_dc(pws, queue, rows)
    for corner, cs in capq.items():
        u = lambda n, k: n if n == '0' else f'{n}_{k}'
        insts = [(cell, p, [u(n, k) for n in nets], [f'Port:P{k + 1} {u(nets[0], k)} 0 Num={k + 1} Z=50 Ohm'])
                 for k, (_, cell, p, nets, _, _) in enumerate(cs)]
        with tempfile.TemporaryDirectory() as t:
            out = f'{t}/c.s{len(cs)}p'
            pdk_bench(pws, f'C{corner}', {c[0] for c in cs}, insts,
                      'analysis SP1 type=sparam start=1 stop=1 npts=1 Unit=GHz', 'sparam', '-o', out)
            for (_, _, _, _, label, cref), got in zip(cs, caps_from_snp(out)):
                check('pdk:// ' + label, got, cref, 0.01, rows)
    hb(kit, ws, rows)
    noise(kit, ws, pws, rows)
    osc(kit, ws, rows)
    return rows


def osc(kit, ws, rows):
    """The VCO_PhaseNoise example's circuit (npn13G2 Nx=4 common-base Colpitts, 1 nH and 4 ohm tank,
    each MIM capacitor as its 436.2 fF and 55 mOhm): circuitRF's oscillator analysis against an ngspice
    transient on the same compiled VBIC 1.3, for the frequency and the collector's fundamental."""
    b = bench(ws, kit, 'npn13G2', {'Nx': 4}, {'c': 'c', 'b': 'vb', 'e': 'e', 'bn': '0'}, [])
    parts = [('Vdc:VCC vcc 0 Vdc=2.0 V', 'VCC vcc 0 2.0'), ('Vdc:VB sb 0 Vdc=1.6 V', 'VB sb 0 1.6'),
             ('R:RB sb vb R=1k', 'RB sb vb 1k'), ('C:CBB vb 0 C=10 pF', 'CBB vb 0 10p'),
             ('L:L1 vcc t L=1 nH', 'L1 vcc t 1n'), ('R:R1 t c R=4', 'R1 t c 4'), ('R:RE e 0 R=1k', 'RE e 0 1k'),
             ('R:RC1 c m1 R=0.055', 'RC1 c m1 0.055'), ('C:C1 m1 e C=436.2 fF', 'C1 m1 e 436.2f'),
             ('R:RC2 e m2 R=0.055', 'RC2 e m2 0.055'), ('C:C2 m2 0 C=436.2 fF', 'C2 m2 0 436.2f')]
    with tempfile.TemporaryDirectory() as t:
        crf('netlist', b, '-o', f'{t}/o.cnl')
        cnl = open(f'{t}/o.cnl').read()
        open(f'{t}/o.cnl', 'w').write(cnl + '\n'.join([p for p, _ in parts] + [
            'OscProbe:OP1 c 0 Mode=shunt', 'analysis OSC1 type=osc Fguess=10 Unit=GHz MaxHarm=9']) + '\n')
        crf('osc', f'{t}/o.cnl', '-o', f'{t}/o.txt')
        txt = open(f'{t}/o.txt').read()
        fosc = float(re.search(r'^# OSC1\.Fosc\nvalue\n(\S+)', txt, re.M)[1])
        vsec = re.search(r'^# OSC1\.V\n(.*?)(?=\n# |\Z)', txt, re.M | re.S)[1]
        v1 = abs(complex(*map(float, re.search(r'^c\t1\t(\S+)\t(\S+)$', vsec, re.M).groups())))
        deck = ['* vco', '.temp 27'] + define_to_ngspice(cnl, ['c', 'vb', 'e', '0'], {'Nx': 4}) + \
               [n for _, n in parts] + ['.ic v(c)=1.95', '.control', 'tran 0.05p 40n 0 0.05p',
                                        'meas tran t1 when v(c)=2 rise=300', 'meas tran t2 when v(c)=2 rise=380',
                                        'let f0 = 80/(t2-t1)', 'print f0', 'fourier $&f0 v(c)', '.endc', '.end']
        open(f'{t}/n.cir', 'w').write('\n'.join(deck) + '\n')
        out = subprocess.run(['ngspice', '-b', 'n.cir'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, cwd=t).stdout
    f0 = float(re.search(r'^f0\s*=\s*(\S+)', out, re.M)[1])
    a1 = float(re.search(r'^\s*1\s+\S+\s+(\S+)', out.split('Fourier analysis for v(c)')[1], re.M)[1])
    check('OSC npn13G2 Nx=4 Colpitts  Fosc Hz', fosc, f0, 5e-4, rows)
    check('OSC npn13G2 Nx=4 Colpitts  |V(c)| fundamental', v1, a1, 0.01, rows)


def noise_from_snp(path):
    """(f in Hz, NFmin dB, Gamma_opt, Rn/R, R) per row of a two-port Touchstone file's noise block."""
    opt = next(l for l in open(path) if l.startswith('#')).upper().split()
    v = [[float(x) for x in l.split('!')[0].split()] for l in open(path) if l.strip() and l[0] not in '!#']
    units = {'HZ': 1, 'KHZ': 1e3, 'MHZ': 1e6, 'GHZ': 1e9}
    r, hz = float(opt[opt.index('R') + 1]), next(units[t] for t in opt if t in units)
    return [(f * hz, nf, cmath.rect(m, math.radians(a)), rn, r) for f, nf, m, a, rn in (x for x in v if len(x) == 5)]


def ngspice_sp(lines, f):
    """ngspice's .sp with donoise on lines at the frequencies f: NF, NFmin (dB), Rn (ohm) and SOpt."""
    n = len(f)
    with tempfile.TemporaryDirectory() as t:
        open(f'{t}/n.cir', 'w').write('\n'.join(lines + ['.control', f'sp lin {n} {f[0]:g} {f[-1]:g} 1',
                                                         'set filetype=ascii', 'write o.raw all', '.endc', '.end']) + '\n')
        subprocess.run(['ngspice', '-b', 'n.cir'], capture_output=True, cwd=t)
        txt = open(f'{t}/o.raw').read()
    names = [m.lower() for m in re.findall(r'^\t\d+\t(\S+)\t', txt.split('Values:')[0], re.M)]
    nums = [complex(float(a), float(b)) for a, b in re.findall(r'(\S+),(\S+)', txt.split('Values:')[1])]
    return {nm: [nums[k * len(names) + i] for k in range(n)] for i, nm in enumerate(names)}


def define_to_ngspice(cnl, nodes, inst):
    """A kit cell's definition, as circuitRF extracts it, in ngspice: its VerilogA device as an OSDI
    instance of the same file, its R and C as they are, the pins renamed to nodes. Parameters are
    evaluated at the typical corner (a ?: assignment takes its last value); internal nodes get an x_ prefix."""
    pins, body = re.search(r'^define \S+ \(([^)]*)\)\n(.*?)^end', cnl, re.M | re.S).groups()
    ren = dict(zip(pins.split(), nodes))
    env = dict(t.split('=') for t in re.search(r'^\s*parameters (.*)$', body, re.M).group(1).split())
    env = {k: float(v) for k, v in env.items()} | inst
    ev = lambda v: eval(v.replace('^', '**'), {}, env)
    lines = []
    for l in body.splitlines():
        if m := re.match(r'^\s*(\w+) = (.*)$', l):
            env[m[1]] = float(re.findall(r'[-0-9.eE]+', m[2])[-1]) if '?' in m[2] else ev(m[2])
            continue
        tok = l.split()
        if not tok or ':' not in tok[0]:
            continue
        kind, name = tok[0].split(':')
        nets = ' '.join(ren.get(t, t if t == '0' else 'x_' + t) for t in tok[1:] if '=' not in t)
        kv = dict(t.split('=', 1) for t in tok[1:] if '=' in t)
        if kind == 'VerilogA':
            osdi = kv.pop('File').strip('"')
            card = ' '.join(f'{k}={ev(v):.10g}' for k, v in kv.items() if k not in ('Pins', 'Temp'))
            lines += ['.control', f'pre_osdi {osdi}', '.endc', f'.model m{name} {STAND_IN["module"]} {card}',
                      f'N{name} {nets} m{name}']
        elif kind in ('R', 'C'):
            lines.append(f'{kind}{name} {nets} {ev(kv[kind]):.10g}')
    return lines


def noise(kit, ws, pws, rows):
    """Small-signal noise between two 50-ohm ports through ideal bias tees, at 16.85 C = T0 (where
    ngspice's noise figure, referred to the circuit temperature, is the IEEE one), against ngspice's
    .sp donoise. The MOSFET is the PDK's own part on both sides (pdk://, PSP 103). The HBT, as the
    kit cell and as the PDK's part with the VBIC 1.3 stand-in, is compared with ngspice running the
    same compiled VBIC 1.3: ngspice's built-in VBIC, which the PDK's cards name, stamps rbp's thermal
    noise across re (vbicnoise.c, ngspice 47), and reads NFmin about 0.05 dB and Rn about 22 % higher."""
    f = (2e9, 8e9, 14e9, 20e9)
    ports = ['Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50', 'Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50']
    tees = lambda vin, vout: ['C1 p1 nb 1u', 'L1 nb sb 1u', f'VB sb 0 {vin}', 'C2 p2 nc 1u', 'L2 sc nc 1u', f'VC sc 0 {vout}']
    crf_tees = lambda vin, vout: ['Port:P1 p1 0 Num=1 Z=50 Ohm', 'Port:P2 p2 0 Num=2 Z=50 Ohm',
                                  'C:CB1 p1 nb C=1 uF', 'L:LB1 nb sb L=1 uH', f'Vdc:VB sb 0 Vdc={vin} V',
                                  'C:CB2 nc p2 C=1 uF', 'L:LC nc sc L=1 uH', f'Vdc:VC sc 0 Vdc={vout} V']
    sp = f'analysis SP1 type=sparam start=2 stop=20 npts={len(f)} Unit=GHz Noise=yes'
    runs = []
    with tempfile.TemporaryDirectory() as t:
        # the HBT: kit cell (its T is its own temperature) and pdk:// part, one ngspice reference
        b = bench(ws, kit, 'npn13G2', {'Nx': 1, 'T': 16.85}, {'c': 'nc', 'b': 'nb', 'e': '0', 'bn': '0'}, [])
        crf('netlist', b, '-o', f'{t}/k.cnl')
        cnl = open(f'{t}/k.cnl').read()
        open(f'{t}/k.cnl', 'w').write(cnl + '\n'.join(crf_tees(0.85, 1.5) + [sp]) + '\n')
        crf('sparam', f'{t}/k.cnl', '-o', f'{t}/k.s2p', '--set', 'temp=16.85')
        ng = ngspice_sp(['* npn13G2', '.temp 16.85'] + define_to_ngspice(cnl, ['nc', 'nb', '0', '0'],
                                                                          {'Nx': 1, 'T': 16.85}) + ports + tees(0.85, 1.5), f)
        runs.append(('npn13G2 Nx=1', noise_from_snp(f'{t}/k.s2p'), ng))
        pdk_bench(pws, 'N_npn13G2', {lib('hbt', 0)}, [('npn13G2', {'Nx': 1}, ['nc', 'nb', '0', '0'], crf_tees(0.85, 1.5))],
                  sp, 'sparam', '-o', f'{t}/p.s2p', '--set', 'temp=16.85')
        runs.append(('pdk:// npn13G2 Nx=1', noise_from_snp(f'{t}/p.s2p'), ng))
        mos, libline = 'w=1e-05 l=1.3e-07 ng=5', '.lib cornerMOSlv.lib mos_tt'
        pdk_bench(pws, 'N_nmos', {libline}, [('sg13_lv_nmos', {'w': 1e-5, 'l': 1.3e-7, 'ng': 5}, ['nc', 'nb', '0', '0'],
                                             crf_tees(0.6, 1.2))], sp, 'sparam', '-o', f'{t}/m.s2p', '--set', 'temp=16.85')
        runs.append((f'pdk:// sg13_lv_nmos {mos}', noise_from_snp(f'{t}/m.s2p'),
                     ngspice_sp(['* nmos', libline, '.temp 16.85', f'X1 nc nb 0 0 sg13_lv_nmos {mos}'] + ports + tees(0.6, 1.2), f)))
    for label, got, ng in runs:
        if len(got) != len(f) or any(abs(g[0] - fk) > 1 for g, fk in zip(got, f)):
            raise RuntimeError(f'{label}: noise block at {[g[0] for g in got]} Hz, not at {f}')
        for k, (fk, nfmin, gopt, rn, r) in enumerate(got):
            # NF from a 50-ohm source, from the file's noise parameters (Gamma_s = 0)
            nf = 10 * math.log10(10 ** (nfmin / 10) + 4 * rn * abs(gopt) ** 2 / abs(1 + gopt) ** 2)
            tag = f'{label} SP noise {fk / 1e9:g} GHz'
            check(tag + '  NF50 dB', nf, ng['nf'][k].real, 1e-3, rows)
            check(tag + '  NFmin dB', nfmin, ng['nfmin'][k].real, 1e-3, rows)
            check(tag + '  Rn ohm', rn * r, ng['rn'][k].real, 1e-3, rows)
            so = ng['sopt'][k]       # compared as complex; the columns show magnitudes
            err = abs(gopt - so) / abs(so)
            rows.append((tag + '  Sopt', abs(gopt), abs(so), err, err <= 1e-3))


def hb(kit, ws, rows):
    """npn13G2 Nx=1 common emitter at 10 GHz: Pout over a drive sweep, kit vs Xyce (PDK model)."""
    pins = list(range(-30, -1, 4))
    def ex(s):
        s.comp('VAR2', 'Var', -2000, -2000, [par('Pin', str(pins[0]))])
        s.comps.append({"InstanceName": "P1", "Symbol": "P1Tone", "X": -1500, "Y": 2000, "Rotation": "R0",
                        "MirrorX": False, "Disable": "None", "Parameters": [
                            {"Name": "Freq", "Expression": "10", "Unit": "GHz", "ShowOnSchematic": True, "Dimension": "Frequency"},
                            {"Name": "Pavl", "Expression": "Pin", "Unit": "dBm", "ShowOnSchematic": True, "Dimension": "Power"},
                            {"Name": "Z", "Expression": "50", "Unit": "", "ShowOnSchematic": True, "Dimension": "Resistance"}]})
        s.stub(-1500, 1800, 0, -100, 'n1'); s.stub(-1500, 2200, 0, 100, '0')
        s.comp('VB', 'Vdc', -800, 2000, [par('Vdc', '0.88', True)])
        s.stub(-800, 1800, 0, -100, 'nb'); s.stub(-800, 2200, 0, 100, 'n1')
        s.two_pin('RL', 'Resistor', 800, 2000, par('R', '50', True), 'vcc', 'nc')
        s.comp('VC', 'Vdc', 1500, 2000, [par('Vdc', '1.5', True)])
        s.stub(1500, 1800, 0, -100, 'vcc'); s.stub(1500, 2200, 0, 100, '0')
        s.comp('M1', 'Meas', 2500, -2000, [par(f'V{k}{c}', f'{c}(HB1.V("nc",{k}))') for k in (1, 2, 3) for c in ('real', 'imag')])
    b = bench(ws, kit, 'npn13G2', {'Nx': 1}, {'c': 'nc', 'b': 'nb', 'e': '0', 'bn': '0'},
              [{"Type": "hb", "Name": "HB1", "Enabled": True, "ToneExpr": "10e9", "ToneExprs": ["10e9"],
                "ToneUnits": ["Hz"], "NumFreqsExpr": "1", "MaxMixOrderExpr": "1", "MaxHarmonicExpr": "11",
                "FFTOverSampleExpr": "1", "TolExpr": "1e-8", "DriveSteppingExpr": "IfNecessary",
                "GuardHarmonicExpr": "0", "LambdaExpr": "1", "MaxIterExpr": "100"},
               {"Type": "sweep", "Name": "SW", "Enabled": True, "PsaVarName": "Pin", "PsaInnerName": "HB1",
                "PsaMode": "StepSize", "PsaStart": pins[0], "PsaStop": pins[-1], "PsaStepOrCount": 4,
                "PsaKind": "Linear"}], ex)
    import numpy as np
    with tempfile.TemporaryDirectory() as t:
        crf('hb', b, '-o', f'{t}/h.npy')
        a = np.load(f'{t}/h.npy')[0]
        kit_pout = [10 * math.log10(abs(complex(a['V1real'][i], a['V1imag'][i])) ** 2 / 100 / 1e-3) for i in range(len(pins))]
        amp = ' '.join('%.6g' % math.sqrt(8 * 50 * 10 ** ((p - 30) / 10)) for p in pins)
        open(f'{t}/x.cir', 'w').write(f"""* HB reference
.lib '{PDK}/libs.tech/xyce/models/cornerHBT.lib' hbt_typ
.param A=0.01
V1 in 0 SIN(0.88 {{A}} 10e9)
R1 in b 50
X1 c b 0 0 npn13G2 Nx=1
VCC vcc 0 1.5
RL vcc c 50
.HB 10e9
.options hbint numfreq=12
.step A list {amp}
.print HB_FD FORMAT=CSV V(c)
.end
""")
        subprocess.run(['Xyce', 'x.cir'], cwd=t, capture_output=True, check=True)
        rr = [l.split(',') for l in open(f'{t}/x.cir.HB.FD.csv')][1:]
        xy = [2 * abs(complex(float(r[1]), float(r[2]))) for r in rr if abs(float(r[0]) - 10e9) < 1]
    for p, k, x in zip(pins, kit_pout, xy):
        xp = 10 * math.log10(x ** 2 / 100 / 1e-3)
        rows.append((f'HB npn13G2 Nx=1 10 GHz Pavs={p} dBm  Pout dBm', k, xp, abs(k - xp) / abs(xp), abs(k - xp) <= 0.2))
    # the same bench with harmonicaRF's DUT: the kit's compiled npn13G2 (Nx only) wired the way
    # harmonicaRF wires an external model (ExtDevice gate drain source = base collector emitter)
    osdi = f'{kit}/models/osdi/npn13G2.osdi'
    with tempfile.TemporaryDirectory() as t:
        open(f'{t}/h.cnl', 'w').write(f"""Pin = {pins[0]}
RFfreq = 10 GHz
P1Tone:P1  n1  0  Num=1  Pavl=Pin dBm  Z=50 Ohm  Freq=RFfreq  Phase=0 deg
Vdc:VB  nb  n1  Vdc=0.88 V
ExtDevice:DUT  nb nc 0  Provider=VerilogA|{osdi} Type=npn13G2  Nx=1
R:RL  vcc  nc  R=50 Ohm
Vdc:VC  vcc  0  Vdc=1.5 V
analysis HB1 type=hb Tone="RFfreq" ToneUnit=GHz MaxHarm=11
analysis SW type=parametric_sweep Var=Pin Start={pins[0]} Stop={pins[-1]} Step=4 Inner=HB1
measure V1re = real(HB1.V("nc",1))
measure V1im = imag(HB1.V("nc",1))
""")
        crf('hb', f'{t}/h.cnl', '-o', f'{t}/h.npy')
        a = np.load(f'{t}/h.npy')[0]
    for i, (p, x) in enumerate(zip(pins, xy)):
        k = 10 * math.log10(abs(complex(a['V1re'][i], a['V1im'][i])) ** 2 / 100 / 1e-3)
        xp = 10 * math.log10(x ** 2 / 100 / 1e-3)
        rows.append((f'harmonicaRF DUT npn13G2.osdi Pavs={p} dBm  Pout', k, xp, abs(k - xp) / abs(xp), abs(k - xp) <= 0.2))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kit', 'IHP_SG13G2'))
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as ws, tempfile.TemporaryDirectory() as pws:
        json.dump({"FormatVersion": 2, "LibraryRefs": [a.kit], "KnownFiles": []}, open(f'{ws}/.cws', 'w'))
        pdk_workspace(pws, os.path.abspath(a.kit))
        rows = run(os.path.abspath(a.kit), ws, pws)
    bad, gaps = 0, []
    for label, got, ref, err, ok in rows:
        gap = not ok and GAPS.get(label)
        bad += not ok and not gap
        gaps += [gap] if gap else []
        print(f"{'ok ' if ok else 'gap' if gap else 'BAD'} {label:52s} kit {got:11.4e}  PDK {ref:11.4e}  {100 * err:6.2f} %")
    print(f'{len(rows) - bad - len(gaps)}/{len(rows)} within tolerance'
          + ''.join(f'; known gap in circuitRF: {g}' for g in gaps))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
