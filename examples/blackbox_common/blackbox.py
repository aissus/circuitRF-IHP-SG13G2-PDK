"""Shared by inductor_coupling/ and hbt_core_matching/: the writers for their cells, layouts and EM setups, the two
coil cells and the TopMetal1 ground plane both use, and the Touchstone arithmetic of their comparisons.

A generator calls ws(<its folder>) first; every writer then writes into that workspace. Coordinates in um.
"""
import copy, json, os, subprocess, sys
import numpy as np

KITREPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')     # the repository's top folder
sys.path.insert(0, os.path.join(KITREPO, 'generator'))
from ihp2crf import Sheet, par          # noqa: E402  (the kit generator's schematic writer)

KIT = 'ws://IHP_SG13G2/'
M1, M2, M3, M4, M5, MIM, TM1, TM2 = 8, 10, 30, 50, 67, 36, 126, 134
V1, V2, V3, V4, TV1 = 19, 29, 49, 66, 125
TECH = '../../tech/IHP_SG13G2.ctech'
TI = 'tech/IHP_SG13G2.ctech'
# The PCell snapshots, under the names circuitRF gives them in .generated-cells (convert --trust-kit of a probe).
BIG, SMALL, NPN = 'inductor2_0d8ac11f9f1f', 'inductor2_e25e3f1e4ecf', 'npn13G2_9bcac288b019'
CAP = {8: 'cmim_48ddc806fb18', 20: 'cmim_ff1bff80e4ba'}            # cmim, a x a um
SNAPS = {BIG: {"GeneratorId": "inductor2", "Parameters": {"w": "5.4u", "s": "4.1u", "d": "62.63u", "nr_r": {"int": 2}},
               "TechIdentity": TI},
         SMALL: {"GeneratorId": "inductor2", "Parameters": {"w": "4u", "s": "2.1u", "d": "35u", "nr_r": {"int": 2}},
                 "TechIdentity": TI},
         NPN: {"GeneratorId": "npn13G2", "Parameters": {"Nx": 1}, "TechIdentity": TI},
         **{n: {"GeneratorId": "cmim", "Parameters": {"w": f"{a}u", "l": f"{a}u"}, "TechIdentity": TI}
            for a, n in CAP.items()}}
# Each coil's two TopMetal1 leads end at y = -1 (facing -y): lead centre x and width, from the generated cells.
LEAD = {BIG: (4.75, 5.4), SMALL: (3.05, 4.0)}
XS = 152.5          # L2's origin: 46.25 (L1's coil edge) + 75 um (the spacing, coil edge to coil edge) + 31.25

FREQ = {"StartExpr": "1", "StopExpr": "40", "NumPoints": 14, "Mode": "PointCount", "Kind": "Linear",
        "StartUnit": "GHz", "StopUnit": "GHz"}                         # 1, 4, 7, ... 40 GHz
PMESH = {"Auto": True, "CellsPerWavelength": 20, "EdgeMesh": False, "EdgeCells": 3, "MinCellsAcrossConductor": 2}
TOP = ["TopMetal1", "TopMetal2"]
ALL = ["Metal1", "Metal2", "Metal3", "Metal4", "Metal5", "MIM", "TopMetal1", "TopMetal2"]
_WS = None


def ws(folder):
    global _WS
    _WS = os.path.abspath(folder)


def d(v):
    return int(round(v * 1000))


def rect(layer, x0, y0, x1, y1):
    return {"$type": "Rect", "X1": d(min(x0, x1)), "Y1": d(min(y0, y1)), "X2": d(max(x0, x1)), "Y2": d(max(y0, y1)),
            "Layer": {"Layer": layer, "Datatype": 0}}


def poly(layer, pts, holes=()):
    p = {"$type": "Poly", "Layer": {"Layer": layer, "Datatype": 0}, "Xy": [d(v) for xy in pts for v in xy]}
    if holes:
        p["Holes"] = [[d(v) for xy in h for v in xy] for h in holes]
    return p


def port(text, x, y, direction, layer, sid=None):
    p = {"$type": "Label", "X": d(x), "Y": d(y), "Text": text, "Height": 2000, "Rotation": "R0", "IsPort": True,
         "PortDirection": direction, "PortLayer": {"Layer": layer, "Datatype": 0}, "Style": "Regular",
         "PortUncalibrated": True,   # a calibrated feed refuses on this die (metal within the standards' clearance)
         "Layer": {"Layer": layer, "Datatype": 0}}
    if sid:
        p["SchematicId"] = sid
    return p


def inst(ref, x, y, sid):
    return {"CellRef": f'../../.generated-cells/{ref}', "X": d(x), "Y": d(y), "Rot": "R0", "MirrorX": False, "Mag": 1,
            "Rows": 1, "Cols": 1, "PitchX": 0, "PitchY": 0, "SchematicId": sid}


def clay(cell, shapes, instances):
    os.makedirs(f'{_WS}/{cell}/layout', exist_ok=True)
    refs = {i['CellRef'].rsplit('/', 1)[1] for i in instances}
    json.dump({"FormatVersion": 1, "DbuPerMicron": 1000, "DisplayUnit": "Um", "SnapDbu": 5, "AngleMode": "AnyAngle",
               "TechRef": TECH, "PCellSnapshots": {k: v for k, v in SNAPS.items() if k in refs},
               "Shapes": shapes, "Instances": instances}, open(f'{_WS}/{cell}/layout/{cell}.clay', 'w'), indent=1)


def ccell(cell):
    os.makedirs(f'{_WS}/{cell}', exist_ok=True)
    json.dump({"FormatVersion": 1, "Parameters": [], "IsTestBench": False, "Terminals": [], "NumPorts": 0},
              open(f'{_WS}/{cell}/.ccell', 'w'), indent=1)


def write_sheet(s, cell):
    os.makedirs(f'{_WS}/{cell}/schematic', exist_ok=True)
    s.write(f'{_WS}/{cell}/schematic/{cell}.csch')


def term(s, name, num, x, y, net):
    """Term: + pin at (x, y-200), - pin at (x, y+200)."""
    s.comp(name, 'Term', x, y, [par('Num', str(num), True), {"Name": "Z", "Expression": "50", "Unit": "Ohm",
                                                            "ShowOnSchematic": True, "Dimension": "Resistance"}])
    s.stub(x, y - 200, 0, -100, net)
    s.stub(x, y + 200, 0, 100, '0')


def kit_part(s, name, cell, x, y, params, nets):
    """A kit cell (Generic + ws:// CellRef) with each symbol pin stubbed to its net."""
    sym = json.load(open(f'{KITREPO}/kit/IHP_SG13G2/{cell}/symbol/{cell}.csym'))
    s.comps.append({"InstanceName": name, "Symbol": "Generic", "X": x, "Y": y, "Rotation": "R0", "MirrorX": False,
                    "Disable": "None", "Parameters": [par(k, str(v), True) for k, v in params.items()],
                    "CellRef": KIT + cell})
    for p in sym['Pins']:
        px, py = p['LocalX'], p['LocalY']
        s.stub(x + px, y + py, (100 if px > 0 else -100 if px < 0 else 0), (100 if py > 0 else -100 if py < 0 else 0),
               nets[p['Name']])


def coil(s, name, cell, x, y, la, lb):
    """One of the coil cells (pins LA at -200, LB at +200)."""
    s.comps.append({"InstanceName": name, "Symbol": "Generic", "X": x, "Y": y, "Rotation": "R0", "MirrorX": False,
                    "Disable": "None", "Parameters": [], "CellRef": f'../../{cell}'})
    s.stub(x - 200, y, -100, 0, la)
    s.stub(x + 200, y, 100, 0, lb)


def cem(cell, name, levels, cports, snp=True, freq=FREQ):
    os.makedirs(f'{_WS}/{cell}/em', exist_ok=True)
    doc = {"FormatVersion": 1, "Name": name, "LayoutRef": f'{cell}/layout/{cell}.clay', "Frequency": freq,
           "DispersionCorrection": True, "CreateSnpSchematic": snp, "AnalysisKind": "Planar",
           "AnalysisLevelNames": levels, "PlanarMesh": PMESH}
    if cports:
        doc["ComponentPorts"] = cports
    json.dump(doc, open(f'{_WS}/{cell}/em/{name}.cem', 'w'), indent=1)


def coil_cells():
    """IND_BIG and IND_SMALL: layout = the PCell alone with a drawn port on each lead's end (its own EM run, ind_big /
    ind_small); schematic = that run's 2-port between pins LA and LB, the model a cut puts back."""
    for cell, ref, em in (('IND_BIG', BIG, 'ind_big'), ('IND_SMALL', SMALL, 'ind_small')):
        ccell(cell)
        xl, _ = LEAD[ref]
        clay(cell, [port('1', -xl, -1, 'R90', TM1), port('2', xl, -1, 'R90', TM1)], [inst(ref, 0, 0, 'L')])
        cem(cell, em, TOP, None, snp=False)
        s = Sheet(cell)
        s.comp('S1', 'Snp', 0, 0, [par('NumPorts', '2'), par('File', f'"results/{em}.s2p"')])
        s.stub(-200, 0, -100, 0, 'LA')
        s.stub(200, 0, 100, 0, 'LB')
        for i, n in enumerate(('LA', 'LB')):
            s.comp(f'PIN{i + 1}', 'Pin', -1000, 500 + 200 * i, [par('Num', str(i + 1), True), par('Name', n)])
            s.stub(-900, 500 + 200 * i, 100, 0, n)
        write_sheet(s, cell)
        os.makedirs(f'{_WS}/{cell}/symbol', exist_ok=True)
        L = lambda x1, y1, x2, y2: {"$type": "Line", "ColorRole": "SymbolLine", "StrokeTier": "Normal",
                                    "X1": x1, "Y1": y1, "X2": x2, "Y2": y2}
        json.dump({"FormatVersion": 6, "GridSize": 100, "PortCount": 2,
                   "Primitives": [L(-200, 0, -100, 0), L(100, 0, 200, 0), L(-100, -50, 100, -50), L(100, -50, 100, 50),
                                  L(100, 50, -100, 50), L(-100, 50, -100, -50)],
                   "Pins": [{"LocalX": -200, "LocalY": 0, "PortIndex": 0, "Name": "LA"},
                            {"LocalX": 200, "LocalY": 0, "PortIndex": 1, "Name": "LB"}]},
                  open(f'{_WS}/{cell}/symbol/{cell}.csym', 'w'), indent=1)


# The TopMetal1 ground plane. Cleared: each coil's IND keep-out box (the coil plus 30 um, as the PCell marks it) and
# a 70 um channel below both, for the feeds or the core. The plane stays between the two keep-outs, a 15 um strip.
YC = -70.0
CLEAR = [(-76.25, YC), (XS + 61.25, YC), (XS + 61.25, 122.5), (XS - 61.25, 122.5), (XS - 61.25, 0),
         (76.25, 0), (76.25, 152.5), (-76.25, 152.5)]
OUTER = [(-100, -100), (XS + 85, -100), (XS + 85, 175), (-100, 175)]
PLANE = poly(TM1, OUTER, [CLEAR])
TIE_X, TIE_Y = -100, 37.5          # the tie: a drawn port on the plane's left edge, shorted to the reference


def lead(ref, x0, side):
    xl, w = LEAD[ref]
    return x0 + side * xl, w


# ------------------------------------------------------------------ Touchstone arithmetic for the comparisons
def touchstone(path):
    """(f in GHz, S[f, i, j], Z0) from a Touchstone v1 file (RI, MA or DB; Hz..GHz)."""
    n = int(os.path.splitext(path)[1][2:-1])
    fmt, vals = None, []
    for line in open(path):
        line = line.split('!')[0].strip()
        if not line:
            continue
        if line.startswith('#'):
            fmt = line.upper().split()
            continue
        vals += [float(x) for x in line.split()]
    unit = {'HZ': 1e-9, 'KHZ': 1e-6, 'MHZ': 1e-3, 'GHZ': 1}[fmt[1]]
    z0 = float(fmt[fmt.index('R') + 1])
    rows = np.array(vals).reshape(-1, 1 + 2 * n * n)
    a, b = rows[:, 1::2], rows[:, 2::2]
    s = {'RI': a + 1j * b, 'MA': a * np.exp(1j * np.radians(b)),
         'DB': 10 ** (a / 20) * np.exp(1j * np.radians(b))}[fmt[3]].reshape(-1, n, n)
    if n == 2:
        s = s.transpose(0, 2, 1)          # a 2-port's rows are S11 S21 S12 S22
    return rows[:, 0] * unit, s, z0


def write_s(path, f, s, z0, note):
    """A Touchstone v1 file in RI, row-major per frequency (n > 2)."""
    with open(path, 'w') as o:
        o.write(f'! {note}\n# GHz S RI R {z0:g}\n')
        for fi, m in zip(f, s):
            o.write(f'{fi:g} ' + ' '.join('%.10g %.10g' % (x.real, x.imag) for x in m.reshape(-1)) + '\n')


def y_of(s, z0):
    e = np.eye(s.shape[-1])
    return (e - s) @ np.linalg.inv(e + s) / z0


def s_of(y, z0):
    e = np.eye(y.shape[-1])
    return (e - z0 * y) @ np.linalg.inv(e + z0 * y)


def keep(y, ports):
    """The ports not listed are shorted: the admittance matrix of the rest (1-based port numbers)."""
    i = [p - 1 for p in ports]
    return y[:, i][:, :, i]


def row(name, f, v, fmt, at):
    print('%-28s' % name + ''.join('%9s' % (fmt % v[np.argmin(abs(f - g))]) for g in at))


def display(name, files, pairs):
    """name.cdd: one plot per (i, j), |S(i,j)| in dB of every file in it, and its picture pictures/name.png
    (inside the image: it runs circuitrf plot and render)."""
    os.makedirs('pictures', exist_ok=True)
    args = ['circuitrf', 'plot', files[0][1], '-o', f'pictures/{name}.png', '--write-cdd', f'{name}.cdd']
    for i, j in pairs:
        args += ['--trace', f'cube=S,i={i},j={j},y=db20,label=S{i}{j}']
    subprocess.run(args, check=True, capture_output=True)
    doc = json.load(open(f'{name}.cdd'))
    p0 = doc['Tabs'][0]['Plots'][0]
    plots = []
    for q, t0 in enumerate(p0['Traces']):
        p = copy.deepcopy(p0)
        p['Left'], p['Top'], p['Traces'] = q % 2 * (p0['Width'] + 20), q // 2 * (p0['Height'] + 20), []
        for c, (label, path) in enumerate(files):
            t = copy.deepcopy(t0)
            t['SourcePath'], t['Label'] = path, f'{label} {t0["Label"]}'
            t['Properties']['LineColorIndex'] = t['Properties']['MarkerColorIndex'] = (1, 2, 6)[c]          # blue, red, green
            p['Traces'].append(t)
        plots.append(p)
    doc['Tabs'][0]['Plots'] = plots
    json.dump(doc, open(f'{name}.cdd', 'w'), indent=1)
    subprocess.run(['circuitrf', 'render', f'{name}.cdd', '-o', f'pictures/{name}.png'], check=True,
                   capture_output=True)


if __name__ == '__main__':
    # self-check: a series 600 pH + 2 Ohm between two 50 Ohm ports, port 2 shorted, gives L and R back
    w = 2e9 * np.pi * 10
    zs = 2 + 1j * w * 600e-12
    z11 = 1 / keep(y_of(s_of(np.array([[[1, -1], [-1, 1]]]) / zs, 50), 50), [1])[0, 0, 0]
    assert abs(z11.imag / w - 600e-12) < 1e-15 and abs(z11.real - 2) < 1e-9, z11
    print('blackbox.py check: ok')
