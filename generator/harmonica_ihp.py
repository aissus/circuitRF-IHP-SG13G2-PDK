#!/usr/bin/env python3
"""IHP SG13G2 HBTs in harmonicaRF (circuitRF's interactive harmonic load-pull).

harmonicaRF takes ONE compiled device with exactly three terminals in the order
gate, drain, source. The stock VBIC models are (c,b,e,s[,dt]), so this builds
VBIC 1.3 as (b,c,e): base, collector, emitter in that order, the thermal node
internal (self-heating on, as the PDK's selft=1), and the PDK's substrate
network (Rsub || Csub from the substrate node to ground) built in.

  harmonica_ihp.py nx-osdi <device> <out.osdi>
        the device itself (module npn13G2, npn13G2l or npn13G2v): every VBIC
        parameter hidden and set from the PDK's own expressions, so its only
        parameters are Nx (and le on npn13G2l/v), corner (0 typ, 1 bcs, 2 wcs)
        and temp
  harmonica_ihp.py osdi  <out.osdi>
        the plain vbic13_bce (all VBIC parameters open), kept for older documents
  harmonica_ihp.py charm <out.charm> [--device npn13G2] [--nx 8] [--corner typ]
        [--temp 27] [--vbe 0.74] [--vce 1.6] [--f 50e9] [--harmonics 5]
        [--zs 17.1+35.8j] [--zl 42.7-7.6j] [--pavl 4] [--osdi PATH]
  (the DUT is the kit's <device>.osdi with Nx, corner and temp; --zs, --zl and --pavl default to
   the Nx=8 starting point scaled to the size: Z by 8/Nx, drive by 10*log10(Nx/8))
"""
import argparse, json, math, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VBIC_SRC = '/foss/tools/vacask/src/vacask/devices/vbic'
OSDI = os.path.join(HERE, '..', 'kit', 'IHP_SG13G2', 'models', 'osdi')


def build_osdi(out):
    with tempfile.TemporaryDirectory() as t:
        for f in os.listdir(VBIC_SRC):
            shutil.copy(os.path.join(VBIC_SRC, f), t)
        src = open(os.path.join(t, 'vbic_1p3.va')).read()
        for a, b in [('module vbic13_4t(c,b,e,s);', 'module vbic13_bce(b,c,e);'),
                     ('inout       c,b,e,s;                         // external nodes',
                      'inout       b,c,e;                           // external nodes (s is internal)'),
                     ('analog begin : analogBlock',
                      '// IHP PDK substrate network, substrate node to ground\n'
                      'parameter real rsub = 400     from (0:inf);\n'
                      'parameter real csub = 2.15e-14 from [0:inf);\n'
                      'analog begin : analogBlock\n'
                      '    I(s) <+ V(s)/rsub;\n'
                      '    I(s) <+ ddt(csub*V(s));')]:
            assert src.count(a) == 1, a
            src = src.replace(a, b)
        open(os.path.join(t, 'vbic_bce.va'), 'w').write(src)
        subprocess.run(['openvaf', 'vbic_bce.va', '-o', os.path.abspath(out)], cwd=t, check=True)


def _va(expr):
    """A circuitRF expression (ihp2crf.translate) in Verilog-A: x^y -> pow(x,y), if() -> ?:."""
    import ihp2crf
    e = ihp2crf._replace_call(expr, 'if', lambda a: f'(({a[0]}) ? ({a[1]}) : ({a[2]}))')
    e = re.sub(r'(?<![\w.])\.(\d)', r'0.\1', e)    # .00E-04 (as the PDK writes ikp): Verilog-A needs the 0
    while '^' in e:
        i = e.index('^')
        j = i - 1                                   # left operand: a (...) group or a name/number
        if e[j] == ')':
            depth = 0
            while True:
                depth += e[j] == ')'; depth -= e[j] == '('
                if depth == 0: break
                j -= 1
        else:
            while j > 0 and (e[j - 1].isalnum() or e[j - 1] in '._'): j -= 1
        k = i + 1                                   # right operand, the same way
        if e[k] == '(':
            depth = 0
            while True:
                depth += e[k] == '('; depth -= e[k] == ')'
                if depth == 0: break
                k += 1
            k += 1
        else:
            if e[k] in '+-': k += 1
            while k < len(e) and (e[k].isalnum() or e[k] in '._'): k += 1
        e = f'{e[:j]}pow({e[j:i]},{e[i + 1:k]}){e[k:]}'
    return re.sub(r'(?<![\w.])T(?![\w.])', 'pdk_T', e)


def nx_source(device):
    """The PDK's own scaling of this device, as Verilog-A declarations.

    Returns (declarations, defaults, rsub, csub, user): the parameters left to the user (Nx, le
    where the device has it, corner, temp), localparams for every other subcircuit parameter and
    corner multiplier, one localparam per model-card value (pdk_card_<name>), and the substrate
    network's expressions. Everything is the PDK's expression of the user parameters, unresolved."""
    import ihp2crf as k
    m = os.path.join(os.environ['PDKPATH'], 'libs.tech/ngspice/models')
    lines = k.logical_lines(k.read(f'{m}/sg13g2_hbt_mod.lib'))
    cornerlib = k.logical_lines(k.read(f'{m}/cornerHBT.lib'))
    _, body = k.subckt(lines, device)
    sub = [kv for l in body if l.lower().startswith('.param') for kv in k.assignments(l[6:])]
    inst = next(l for l in body if l[0].upper() in 'QN' and not l.startswith('.'))
    model = [t for t in inst.split()[1:] if '=' not in t][-1]
    _, card = k.model_card(lines, model)
    wanted = {w.lower() for _, v in sub + card for w in re.findall(r'[A-Za-z_]\w*', v)}
    cvars = k.corner_vars(cornerlib, 'hbt', wanted)

    # what the PDK lets a user set: Nx, and le on the long and high-voltage devices (npn13G2's is fixed)
    user = [n for n, _ in sub if n.lower() == 'nx' or (n.lower() == 'le' and device.lower() != 'npn13g2')]
    names = {n.lower(): 'pdk_' + n for n, _ in sub}
    names.update({n.lower(): 'pdk_' + n for n in cvars})
    names.update({u.lower(): u for u in user}, corner='corner', t='pdk_T')
    tr = lambda e: _va(k.translate(e, names))

    sub_d = dict(sub)
    decl = ['// IHP SG13G2 %s: the PDK\'s own scaling, in Nx%s, corner and temp' % (device, ', le' if 'le' in user else '')]
    decl.append('parameter real Nx = %s from [1:10];' % tr(sub_d['Nx']))
    if 'le' in user:
        decl.append('parameter real le = %s from (0:inf);' % tr(sub_d['le']))
    decl += ['parameter integer corner = 0 from [0:2];   // 0 typ, 1 bcs, 2 wcs',
             'parameter real temp = 27;                  // degC',
             'localparam real pdk_T = temp;']
    decl += [f'localparam real pdk_{n} = {tr(v)};' for n, v in cvars.items()]
    decl += [f'localparam real pdk_{n} = {"0" if n.lower() == "dtemp" else tr(v)};'
             for n, v in sub if n not in user]
    defaults = {}
    for n, v in card:
        if n.lower() in ('level', 'vbe_max', 'vbc_max', 'vce_max', 'type'):
            continue
        decl.append(f'localparam real pdk_card_{n.lower()} = {tr(v)};')
        defaults[n.lower()] = f'pdk_card_{n.lower()}'
    # harmonicaRF and circuitRF run devices at 26.85 C; VBIC's own offset brings it to temp
    defaults['trise'] = '(temp - 26.85)'
    rc = {t[0].lower(): dict(k.assignments(l)) for l in body if (t := l.split())[0][0].upper() in 'RC'}
    rsub = tr(rc['rsub'].get('R') or rc['rsub'].get('r') or next(iter(rc['rsub'].values())))
    csub = tr(rc['csub'].get('C') or rc['csub'].get('c') or next(iter(rc['csub'].values())))
    return '\n'.join(decl), defaults, rsub, csub, user


def build_nx_osdi(device, out):
    """VBIC 1.3 (b,c,e) with every VBIC parameter made an internal variable, set from the PDK's
    expression of Nx (and le), corner and temp: a compiled device whose only parameters are the
    device's own. Module name = the device name, so Set DUT shows e.g. npn13G2 with Nx, corner, temp."""
    decl, defaults, rsub, csub, user = nx_source(device)
    with tempfile.TemporaryDirectory() as t:
        for f in os.listdir(VBIC_SRC):
            shutil.copy(os.path.join(VBIC_SRC, f), t)
        # $param_given takes parameters only: "given" is decided here, as whether the PDK card sets it
        given = lambda s: re.sub(r'(?:\$param_given|`TESTGIVEN)\((\w+)\)',
                                 lambda mm: '1' if mm[1].lower() in defaults else '0', s)
        m = os.path.join(t, 'cmcGeneralMacrosAndDefines.va')
        text = given(open(m).read())
        open(m, 'w').write(text)
        src = given(open(os.path.join(t, 'vbic_1p3.va')).read())
        for a, b in [('module vbic13_4t(c,b,e,s);', f'module {device}(b,c,e);'),
                     ('inout       c,b,e,s;                         // external nodes',
                      'inout       b,c,e;                           // external nodes (s is internal)\n' + decl),
                     ('analog begin : analogBlock',
                      '// IHP PDK substrate network, substrate node to ground\n'
                      f'localparam real rsub = {rsub};\n'
                      f'localparam real csub = {csub};\n'
                      'analog begin : analogBlock\n'
                      '    I(s) <+ V(s)/rsub;\n'
                      '    I(s) <+ ddt(csub*V(s));')]:
            assert src.count(a) == 1, a
            src = src.replace(a, b)
        src = re.sub(r'^`ALIAS\(.*\n', '', src, flags=re.M)
        # every VBIC parameter (one CMC macro line each: `MPRnb(name, default, ...)) with the PDK's value
        done = set()
        def vbic(mm):
            n = mm[2]
            done.add(n.lower())
            return f"localparam {'integer' if mm[1][2] == 'I' else 'real'} {n} = {defaults.get(n.lower(), mm[3].strip())};"
        src = re.sub(r'^\s*`([MI]P\w*)\(\s*(\w+)\s*,\s*([^,]+),.*$', vbic, src, flags=re.M)
        missing = set(defaults) - done
        if missing: print(f'{device}: PDK values with no VBIC parameter: {sorted(missing)}', file=sys.stderr)
        # OpenVAF exports localparams as parameters: make each a variable, set first in the analog
        # block in declaration order (so each sees the ones it is computed from)
        sets = []
        def var(mm):
            sets.append(f'    {mm[2]} = {mm[3]};')
            return f'{mm[1]} {mm[2]};'
        src = re.sub(r'localparam (real|integer) (\w+)\s*=\s*([^;]+);', var, src)
        src = src.replace('analog begin : analogBlock\n', 'analog begin : analogBlock\n' + '\n'.join(sets) + '\n', 1)
        open(os.path.join(t, f'{device}.va'), 'w').write(src)
        subprocess.run(['openvaf', f'{device}.va', '-o', os.path.abspath(out)], cwd=t, check=True)
        print(f'{out}: module {device}(b,c,e), parameters {", ".join(user)}, corner, temp')


# Starting point for Nx=8 at 50 GHz (the matched source and the load of the kit's example); other
# sizes start from it scaled by 8/Nx, since the device's impedances scale inversely with its size.
ZS8, ZL8, PAVL8 = 17.1 + 35.8j, 42.7 - 7.6j, 4.0


def charm(a):
    osdi = os.path.abspath(a.osdi or f'{OSDI}/{a.device}.osdi')
    z = lambda s: complex(s.replace(' ', ''))
    zs = z(a.zs) if a.zs else ZS8 * 8 / a.nx
    zl = z(a.zl) if a.zl else ZL8 * 8 / a.nx
    if a.pavl is None:
        a.pavl = round(PAVL8 + 10 * math.log10(a.nx / 8), 1)
    doc = {
        "FormatVersion": 1,
        "Dut": {"Kind": "External", "TypeName": a.device, "Provider": "VerilogA|" + osdi,
                "Multiplicity": 1, "ModelFile": osdi,
                "Parameters": {"Nx": f'{a.nx:g}', "corner": str(['typ', 'bcs', 'wcs'].index(a.corner)),
                               "temp": f'{a.temp:g}'},
                # where harmonicaRF reads Idq and the loadline: the device's own current at that node.
                # An internal node's (bi, ci) is zero by KCL, so the terminals, emitter grounded.
                "IntrinsicGate": "b", "IntrinsicDrain": "c", "IntrinsicSource": "e"},
        "Bias": {"Vgs": a.vbe, "Vds": a.vce},
        "Settings": {"HarmonicCount": a.harmonics, "FrequencyHz": a.f, "Z0": 50.0, "CompressionDb": 1.0,
                     "DcivVgsMin": a.vbe - 0.15, "DcivVgsMax": a.vbe + 0.12, "DcivVgsSteps": 6,
                     "DcivVdsMin": 0.0, "DcivVdsMax": 2 * a.vce + 0.4, "DcivVdsSteps": 41},
        "PavlDbm": a.pavl,
        "Terminations": {"source:1": f"{zs.real!r},{zs.imag!r}", "load:1": f"{zl.real!r},{zl.imag!r}"},
        # the extrinsic plane's DC-IV family is solved point by point; the intrinsic one evaluates
        # the model with its internal nodes at 0 V, which for VBIC is Vce/rcx, not a transistor
        "Appearance": {"LoadlinePlane": "extrinsic"},
    }
    json.dump(doc, open(a.out, 'w'), indent=2)
    print(f'{a.out}: {a.device} Nx={a.nx} {a.corner} {a.temp} C, VBE {a.vbe} V, VCE {a.vce} V, '
          f'{a.f / 1e9:g} GHz, ZS {zs}, ZL {zl}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    o = sub.add_parser('osdi'); o.add_argument('out')
    x = sub.add_parser('nx-osdi'); x.add_argument('device'); x.add_argument('out')
    c = sub.add_parser('charm'); c.add_argument('out')
    c.add_argument('--device', default='npn13G2'); c.add_argument('--nx', type=float, default=8)
    c.add_argument('--corner', default='typ'); c.add_argument('--temp', type=float, default=27)
    c.add_argument('--vbe', type=float, default=0.74); c.add_argument('--vce', type=float, default=1.6)
    c.add_argument('--f', type=float, default=50e9); c.add_argument('--harmonics', type=int, default=5)
    c.add_argument('--zs'); c.add_argument('--zl')      # default: the Nx=8 values scaled by 8/Nx
    c.add_argument('--pavl', type=float); c.add_argument('--osdi')   # default: the kit's <device>.osdi
    a = ap.parse_args()
    if a.cmd == 'osdi': build_osdi(a.out)
    elif a.cmd == 'nx-osdi': build_nx_osdi(a.device, a.out)
    else: charm(a)


if __name__ == '__main__':
    main()
