#!/usr/bin/env python3
"""Every IHP PCell circuitRF offers from the PDK, drawn by circuitRF and compared with KLayout drawing the same cell:

    python3 generator/check_ihp_pcells.py --kit kit/IHP_SG13G2

Writes a scratch workspace, imports the PDK into it (circuitrf import pdk, which declares the PDK's
PCell library, sg13g2_pycell_lib, in ihp-sg13g2-pcells/), places each generator at its defaults and at
the parameter sets below, has circuitRF build it (circuitrf convert --trust-kit), and runs itself again
inside KLayout, which draws each cell through the PDK's own library and XORs it, layer by layer,
against circuitRF's. The kit gives the technology. One line per cell; exit 1 when a cell is not drawn
or differs.

KLayout-only parameters: Calculate = R (resistors) or C (cmim) makes KLayout take w and l as given,
as circuitRF does (its default Calculate = l derives l from R in a callback circuitRF does not run),
and the inductors are compared with subE = true, since KLayout's wrapper draws the LBE etch window
for subE = false too (bool('false') is True).
"""
import argparse, glob, json, os, re, runpy, shutil, subprocess, sys, tempfile

CASES = [  # (generator, parameters as a .clay snapshot holds them): the string ones as circuitRF writes them
    ('npn13G2', {'Nx': {'int': 4}}), ('npn13G2', {'Nx': {'int': 8}}),
    ('npn13G2L', {'Nx': {'int': 2}, 'le': '2.5u'}), ('npn13G2V', {'Nx': {'int': 3}, 'le': '1.5e-06'}),
    ('rsil', {'w': '1u', 'l': '3u'}), ('rppd', {'w': '1e-06', 'l': '2e-06', 'b': '2'}),
    ('rhigh', {'w': '5e-07', 'l': '4u', 'b': '1'}), ('cmim', {'w': '1e-05', 'l': '2e-05'}),
    ('nmos', {'w': '2u', 'ng': '2'}), ('pmosHV', {'w': '1u', 'ng': '3'}),
    ('inductor2', {'subE': True, 'nr_r': {'int': 2}}), ('rfcmim', {'w': '10u', 'l': '10u'}),
]
KLAYOUT_ONLY = {'rsil': {'Calculate': 'R'}, 'rppd': {'Calculate': 'R'}, 'rhigh': {'Calculate': 'R'},
                'cmim': {'Calculate': 'C'}}
DEFAULTS_OVERRIDE = {'inductor2': {'subE': True}, 'inductor3': {'subE': True}}


def generator_ids(entry):
    """What the declaration's entry script registers, asked in-process with circuitRF's own Python package."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(shutil.which('circuitrf'))), 'pcell-python'))
    sys.path.insert(0, os.path.join(os.environ['PDKPATH'], 'libs.tech', 'klayout', 'python'))
    import circuitrf_pcell as crf
    crf.run = lambda *a, **k: None
    runpy.run_path(entry)
    return sorted(crf.default_registry.ids(), key=str.lower)


def build(kit, ws):
    for d in ('tech', 'all/layout'):
        os.makedirs(os.path.join(ws, d))
    shutil.copy(os.path.join(kit, 'tech', 'IHP_SG13G2.ctech'), os.path.join(ws, 'tech'))
    json.dump({'FormatVersion': 2, 'LibraryRefs': [], 'KnownFiles': [], 'DefaultTechRef': 'tech/IHP_SG13G2.ctech'},
              open(os.path.join(ws, '.cws'), 'w'))
    subprocess.run(['circuitrf', 'import', 'pdk', os.environ['PDKPATH'], '--into', ws], check=True,
                   stdout=subprocess.DEVNULL)
    decl = os.path.join(ws, 'ihp-sg13g2-pcells')
    cases = [(g, DEFAULTS_OVERRIDE.get(g, {})) for g in generator_ids(os.path.join(decl, 'kit_entry.py'))] + CASES
    json.dump({'FormatVersion': 1, 'Parameters': [], 'IsTestBench': False, 'Terminals': [], 'NumPorts': 0,
               'PrimaryLayout': 'all.clay'}, open(os.path.join(ws, 'all', '.ccell'), 'w'))
    snaps, inst = {}, []
    for i, (g, p) in enumerate(cases):
        n = 'c%02d' % i
        snaps[n] = {'GeneratorId': g, 'Parameters': p}
        inst.append({'CellRef': '../../.generated-cells/' + n, 'X': i % 8 * 500000, 'Y': i // 8 * 500000,
                     'Rot': 'R0', 'MirrorX': False, 'Mag': 1, 'Rows': 1, 'Cols': 1, 'PitchX': 0, 'PitchY': 0})
    clay = os.path.join(ws, 'all', 'layout', 'all.clay')
    json.dump({'FormatVersion': 1, 'DbuPerMicron': 1000, 'DisplayUnit': 'Um', 'SnapDbu': 5, 'AngleMode': 'AnyAngle',
               'TechRef': '../../tech/IHP_SG13G2.ctech', 'PCellSnapshots': snaps, 'Shapes': [], 'Instances': inst},
              open(clay, 'w'))
    gds = os.path.join(ws, 'all.gds')
    subprocess.run(['circuitrf', 'convert', clay, '-o', gds, '--trust-kit', decl], check=True,
                   stdout=subprocess.DEVNULL)
    drawn = {}                               # generated cell name -> (generator, parameters)
    for f in glob.glob(os.path.join(ws, '.generated-cells', '*', 'layout', '*.clay')):
        o = json.load(open(f))['PCellOrigin']
        drawn[os.path.basename(f)[:-5]] = (o['GeneratorId'], {k: v['int'] if isinstance(v, dict) else v
                                                              for k, v in o['Parameters'].items()})
    missing = len(cases) - len(drawn)
    return gds, drawn, missing


def compare(gds, drawn):
    """Inside KLayout: each circuitRF cell XOR the PDK library's own, per layer."""
    import pya
    k = os.path.join(os.environ['PDKPATH'], 'libs.tech', 'klayout', 'python')
    sys.path += [k, os.path.join(k, 'pycell4klayout-api', 'source', 'python')]
    __import__('sg13g2_pycell_lib')
    A = pya.Layout(); A.read(gds)
    B = pya.Layout(); B.dbu = A.dbu; B.technology_name = 'sg13g2'
    bad = 0
    for c in sorted(A.each_cell(), key=lambda c: (drawn.get(c.name, ('',))[0].lower(), c.name)):
        if c.name not in drawn:
            continue
        g, p = drawn[c.name]
        ref = B.create_cell(g, 'SG13_dev', dict(p, **KLAYOUT_ONLY.get(g, {})))
        shown = ' '.join('%s=%s' % kv for kv in sorted(p.items())) or 'defaults'
        if ref is None:
            print('%-14s %-34s drawn, %.2f x %.2f um; no KLayout cell of that name' % (g, shown, c.dbbox().width(), c.dbbox().height()))
            continue
        diff = []
        for li in sorted(set(A.layer_indexes()) | set(B.layer_indexes())):
            info = (A if li in A.layer_indexes() else B).get_info(li)
            ra = pya.Region(c.begin_shapes_rec(A.layer(info.layer, info.datatype)))
            rb = pya.Region(ref.begin_shapes_rec(B.layer(info.layer, info.datatype)))
            x = (ra ^ rb).area() * A.dbu ** 2
            if x > 1e-6:
                diff.append('%d/%d %.3g um2' % (info.layer, info.datatype, x))
        bad += bool(diff)
        print('%-14s %-34s %s, %.2f x %.2f um' % (g, shown, 'DIFFERS ' + ', '.join(diff) if diff else 'identical',
                                                 c.dbbox().width(), c.dbbox().height()))
    return bad


if 'pya' in sys.modules or 'gds' in globals():          # klayout -b -r this -rd gds=... -rd drawn=...
    sys.exit(1 if compare(gds, json.loads(drawn)) else 0)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--kit', required=True)
    a = ap.parse_args()
    ws = tempfile.mkdtemp(prefix='ihp_pcells_')
    try:
        gds, drawn, missing = build(os.path.abspath(a.kit), ws)
        r = subprocess.run(['klayout', '-b', '-r', os.path.abspath(__file__), '-rd', 'gds=' + gds,
                            '-rd', 'drawn=' + json.dumps(drawn)], capture_output=True, text=True)
        print('\n'.join(l for l in r.stdout.splitlines() if re.match(r'\S+\s+(defaults|\S+=)', l)))
        print('%d of %d cells drawn by circuitRF; %s' % (len(drawn), len(drawn) + missing,
              'all identical to KLayout where it has the cell' if r.returncode == 0 and not missing
              else 'FAILED: a cell is missing or differs'))
        sys.exit(r.returncode or bool(missing))
    finally:
        shutil.rmtree(ws, ignore_errors=True)
