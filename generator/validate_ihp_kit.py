#!/usr/bin/env python3
"""Check the IHP SG13G2 circuitRF kit against the PDK's own models in ngspice.

    python3 validate_ihp_kit.py [--kit /foss/tools/circuitrf/kits/IHP_SG13G2]

Each test places a kit cell in a schematic bench (the way the GUI does: a cell
reference into the library) and runs it with the circuitRF CLI; the same device
runs in ngspice from the PDK's model files. HBTs: Ic and Ib at two VBE, over
devices, Nx, le, corners and temperature. Resistors: R over w, l, b and
corners. MIM capacitor: C at 1 GHz. Exit code 1 if anything is off by more
than the tolerance.
"""
import argparse, cmath, json, math, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ihp2crf import Sheet, par

PDK = os.environ['PDKPATH']
CORNER_LIB = {'hbt': ('cornerHBT.lib', 'hbt'), 'res': ('cornerRES.lib', 'res'), 'cap': ('cornerCAP.lib', 'cap')}
CNAME = ('typ', 'bcs', 'wcs')


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
    r = subprocess.run(['circuitrf', 'cli', verb, path, *args], capture_output=True, text=True)
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


def run(kit, ws):
    rows = []
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
    # ---- MIM capacitor, C at 1 GHz from S11
    for p in ({'w': 7e-6, 'l': 7e-6}, {'w': 20e-6, 'l': 30e-6}, {'w': 20e-6, 'l': 30e-6, 'corner': 2}):
        def ex(s):
            s.comp('P1', 'TermG', 1000, 2000, [par('Num', '1', True), par('Z', '50', True)])
            s.stub(1000, 1800, 0, -100, 'n1'); s.stub(1000, 2200, 0, 100, '0')
        b = bench(ws, kit, 'cap_cmim', p, {'PLUS': 'n1', 'MINUS': '0'},
                  [{"Type": "sp", "Name": "SP1", "Enabled": True,
                    "Sweeps": [{"StartExpr": "1", "StopExpr": "1", "NumPoints": 1, "Mode": "PointCount",
                                "Kind": "Linear", "StartUnit": "GHz", "StopUnit": "GHz"}]}], ex)
        with tempfile.TemporaryDirectory() as t:
            crf('sparam', b, '-o', f'{t}/c.s1p')
            data = [l.split() for l in open(f'{t}/c.s1p') if l.strip() and l[0] not in '!#']
            fmt = next(l for l in open(f'{t}/c.s1p') if l.startswith('#')).upper()
        f, a, bb = map(float, data[0][:3])
        f *= {'HZ': 1, 'KHZ': 1e3, 'MHZ': 1e6, 'GHZ': 1e9}[fmt.split()[1]]
        s11 = complex(a, bb) if ' RI' in fmt else cmath.rect(10 ** (a / 20) if ' DB' in fmt else a, math.radians(bb))
        y = (1 - s11) / (1 + s11) / 50
        got = y.imag / (2 * math.pi * f)
        corner = p.get('corner', 0)
        inst = ' '.join(f'{k}={v}' for k, v in p.items() if k != 'corner')
        ref = ngspice(['* cmim', lib('cap', corner), 'V1 n1 0 dc 0 ac 1', f'X1 n1 0 cap_cmim {inst}',
                       '.control', 'ac lin 1 1e9 1e9', 'print i(V1)', '.endc'])
        cref = -ref['i(v1)'].imag / (2 * math.pi * 1e9)
        check(f'cap_cmim {inst} {CNAME[corner]}  C', got, cref, 0.01, rows)
    hb(kit, ws, rows)
    return rows


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
    ap.add_argument('--kit', default='/foss/tools/circuitrf/kits/IHP_SG13G2')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as ws:
        json.dump({"FormatVersion": 2, "LibraryRefs": [a.kit], "KnownFiles": []}, open(f'{ws}/.cws', 'w'))
        rows = run(os.path.abspath(a.kit), ws)
    bad = 0
    for label, got, ref, err, ok in rows:
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {label:52s} kit {got:11.4e}  PDK {ref:11.4e}  {100 * err:6.2f} %")
    print(f'{len(rows) - bad}/{len(rows)} within tolerance')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
