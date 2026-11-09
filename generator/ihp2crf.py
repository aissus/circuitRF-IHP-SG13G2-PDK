#!/usr/bin/env python3
"""Build a circuitRF device library (cells) from the IHP SG13G2 PDK's ngspice models.

    python3 ihp2crf.py --pdk $PDKPATH --out <libdir>

One cell per device, parameterised like the PDK subcircuit it comes from:

  npn13G2, npn13G2l, npn13G2v   Nx (and le), corner, T, dtemp, selft
  rsil, rppd, rhigh             w, l (and b), m, corner, T, trise
  cap_cmim                      w, l, corner, T
  sg13_{lv,hv}_{nmos,pmos}      w, l, ng, m, corner, T, trise, pre_layout

Every model parameter is written as the PDK's own expression, translated to
circuitRF syntax, so the cell scales with its parameters exactly as the PDK
subcircuit does; nothing is resolved here. The compact models run as OSDI
(VBIC 1.3 five-terminal, CMC R3). Each thermal node goes to ground through the
PDK's own resistor (1e9 ohm), with every terminal of the model declared
(Pins=5 / Pins=4): with fewer, circuitRF builds a different device.

corner: 0 = typ, 1 = bcs, 2 = wcs (the PDK's *_typ/_bcs/_wcs .LIB sections).
Mismatch terms (agauss) are taken at their nominal value: no Monte Carlo.
"""
import argparse, json, os, re

# ---------------------------------------------------------------- PDK reading

def read(path):
    with open(path, 'rb') as f:                     # the IHP libs are ISO-8859-1
        return f.read().decode('iso-8859-1')


def logical_lines(text):
    """ngspice lines with '+' continuations joined and comments removed."""
    out = []
    for raw in text.splitlines():
        line = raw.split('$')[0]
        line = re.sub(r"\s;.*$", '', line)           # inline ; comments
        s = line.strip()
        if not s or s.startswith('*'):
            continue
        if s.startswith('+') and out:
            out[-1] += ' ' + s[1:].strip()
        else:
            out.append(s)
    return out


def assignments(s):
    """name=value pairs in order; a value is a quoted '...' or a bare token."""
    return [(n, v.strip("'")) for n, v in re.findall(r"(\w+)\s*=\s*('[^']*'|[^\s']+)", s)]


def subckt(lines, name):
    """(ports, body lines) of .subckt name, excluding .if/.else alternatives."""
    for i, l in enumerate(lines):
        t = l.split()
        if t[0].lower() == '.subckt' and t[1].lower() == name.lower():
            body, skip = [], False
            for b in lines[i + 1:]:
                low = b.lower()
                if low.startswith('.ends'):
                    break
                if low.startswith('.if'):            # cap_cmim: keep the plain branch
                    continue
                if low.startswith('.else'):
                    skip = True; continue
                if low.startswith('.endif'):
                    skip = False; continue
                if not skip:
                    body.append(b)
            return t[2:], body
    raise KeyError(name)


def model_card(lines, name):
    for l in lines:
        t = l.split()
        if t[0].lower() == '.model' and t[1].lower() == name.lower():
            rest = (l.split(None, 3)[3] if len(t) > 3 else '').strip()
            if rest.startswith('(') and rest.endswith(')'):   # .model x c (A=1 B=2)
                rest = rest[1:-1]
            return t[2].lower(), assignments(rest)
    raise KeyError(name)


def corner_section(lines, section):
    out, inside = {}, False
    for l in lines:
        low = l.lower()
        if low.startswith('.lib ') and len(l.split()) == 2:
            inside = low.split()[1] == section.lower(); continue
        if low.startswith('.endl'):
            inside = False; continue
        if inside and low.startswith('.param'):
            out.update(assignments(l[6:]))
    return out

# ---------------------------------------------------------------- translation

SI = {'t': 12, 'g': 9, 'meg': 6, 'k': 3, 'm': -3, 'u': -6, 'n': -9, 'p': -12, 'f': -15}   # suffix -> decimal exponent


def _replace_call(expr, fname, fn):
    """Replace fname(args) by fn(list of arg strings), paren-aware."""
    while True:
        m = re.search(r'\b%s\s*\(' % fname, expr)
        if not m:
            return expr
        i, depth, args, start = m.end(), 1, [], m.end()
        while depth:
            c = expr[i]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    args.append(expr[start:i])
            elif c == ',' and depth == 1:
                args.append(expr[start:i]); start = i + 1
            i += 1
        expr = expr[:m.start()] + '(' + fn([a.strip() for a in args]) + ')' + expr[i:]


def translate(expr, names):
    """One ngspice expression in circuitRF syntax. names: lowercase -> spelling to use."""
    e = expr.strip().strip("'")
    e = _replace_call(e, 'agauss', lambda a: a[0])          # mismatch off: nominal value
    e = re.sub(r'(?<![\w.])(\d+\.?\d*(?:[eE][-+]?\d+)?)(meg|[tgkmunpf])(?![\w])',
               lambda m: repr(float('%se%d' % (m.group(1), SI[m.group(2).lower()]))), e, flags=re.I)   # 0.34u: 3.4e-07
    e = e.replace('**', '^')
    # A comparison used as a number, as in (postsim>0)*w: circuitRF wants if(...)
    e = re.sub(r'\(([^()?:]*(?:>=|<=|==|!=|>|<)[^()?:]*)\)(?=\s*\*)', r'if(\1,1,0)', e)
    e = re.sub(r'\*\s*\(([^()?:]*(?:>=|<=|==|!=|>|<)[^()?:]*)\)', r'*if(\1,1,0)', e)
    def ident(m):
        w = m.group(0)
        if w.lower() == 'temper':
            return 'T'
        return names.get(w.lower(), w)
    return re.sub(r'(?<![\w.])[A-Za-z_]\w*', ident, e)

# ---------------------------------------------------------------- cell writing

def par(name, expr, show=False):
    return {"Name": name, "Expression": expr, "Unit": "", "ShowOnSchematic": show, "Dimension": "None"}


class Sheet:
    """A cell schematic built from components and labelled wire stubs."""

    def __init__(self, name):
        self.name, self.comps, self.wires, self.labels = name, [], [], []

    def comp(self, inst, symbol, x, y, params, rot='R0'):
        self.comps.append({"InstanceName": inst, "Symbol": symbol, "X": x, "Y": y,
                           "Rotation": rot, "MirrorX": False, "Disable": "None", "Parameters": params})

    def stub(self, x, y, dx, dy, net):
        """A wire from a pin at (x, y) to (x+dx, y+dy), labelled with the net."""
        self.wires.append({"Points": [[x, y], [x + dx, y + dy]]})
        if net == '0':                               # ground: a GND symbol at the stub's end
            self.comp('GND%d' % len(self.wires), 'Ground', x + dx, y + dy, [])
        else:
            self.labels.append({"X": x + dx // 2, "Y": y + dy // 2, "Name": net,
                                "OwnerWireIndex": len(self.wires) - 1, "SegmentIndex": 0,
                                "AlongT": 0.5, "OffsetX": 0, "OffsetY": 0})

    def two_pin(self, inst, symbol, x, y, value_par, n1, n2):
        """R or C, vertical: pin 1 at (x, y-200), pin 2 at (x, y+200)."""
        self.comp(inst, symbol, x, y, [value_par])
        self.stub(x, y - 200, 0, -100, n1)
        self.stub(x, y + 200, 0, 100, n2)

    def write(self, path):
        doc = {"FormatVersion": 2, "CellName": self.name, "GridSize": 100, "GridSnap": True,
               "AuthorGridDivisor": 20, "Components": self.comps, "Wires": self.wires,
               "NetLabels": self.labels, "Dots": [], "CanvasObjects": [],
               "View": {"PanX": 0, "PanY": 0, "Zoom": 1}}
        json.dump(doc, open(path, 'w'), indent=1)


def verilog_a(sheet, x, y, osdi, nets, params):
    """A VerilogA instance with every model terminal declared, pins labelled.
    Pin layout (circuitRF's generic device): (n+1)//2 on the left, the rest on the right."""
    n = len(nets)
    left = (n + 1) // 2
    sheet.comp('Q1', 'VerilogA', x, y,
               [par('File', osdi), par('Pins', str(n))] + [par(k, v) for k, v in params])
    for i, net in enumerate(nets):
        on_left, row = i < left, (i if i < left else i - left)
        count = left if on_left else n - left
        py = y + int((row - (count - 1) / 2) * 200)
        px = x - 200 if on_left else x + 200
        sheet.stub(px, py, -100 if on_left else 100, 0, net)


def terminals(sheet, ports, x0, y0):
    for i, p in enumerate(ports):                     # Pin symbol: its pin is at (+100, 0)
        y = y0 + 200 * i
        sheet.comp('P%d' % (i + 1), 'Pin', x0, y, [par('Num', str(i + 1), True), par('Name', p)])
        sheet.stub(x0 + 100, y, 100, 0, p)


def symbol(path, kind, ports):
    """A small schematic symbol: an HBT, a resistor or a capacitor, pins on the 100 grid."""
    L = lambda x1, y1, x2, y2: {"$type": "Line", "ColorRole": "SymbolLine", "StrokeTier": "Normal",
                                "X1": x1, "Y1": y1, "X2": x2, "Y2": y2}
    T = lambda s, x, y, al='Left': {"$type": "Text", "Content": s, "AnchorX": x, "AnchorY": y,
                                    "FontSize": 16, "FontStyle": "Regular", "Align": al,
                                    "VAlign": "Middle", "Rotation": "R0", "ForceReadable": True,
                                    "ColorRole": "SymbolLine"}
    if kind == 'npn':          # c top, b left, e bottom, bn right
        pos = {'c': (0, -200), 'b': (-200, 0), 'e': (0, 200), 'bn': (200, 0)}
        prims = [L(-200, 0, -40, 0), L(-40, -80, -40, 80), L(-40, -40, 0, -100), L(0, -100, 0, -200),
                 L(-40, 40, 0, 100), L(0, 100, 0, 200), L(0, 100, -26, 92), L(0, 100, -12, 76),
                 L(200, 0, 60, 0), T('bn', 70, -20), T('c', 10, -170), T('e', 10, 170), T('b', -190, -20)]
    elif kind == 'res':        # 1 top, 2 bottom, bn right
        pos = {'1': (0, -200), '2': (0, 200), 'bn': (200, 0), 'PLUS': (0, -200), 'MINUS': (0, 200)}
        zig = [(0, -100), (30, -80), (-30, -40), (30, 0), (-30, 40), (30, 80), (0, 100)]
        prims = [L(0, -200, 0, -100), L(0, 100, 0, 200)] + \
                [L(a[0], a[1], b[0], b[1]) for a, b in zip(zig, zig[1:])] + [L(200, 0, 60, 0), T('bn', 70, -20)]
    elif kind == 'mos':        # d top, g left, s bottom, b right
        pos = {'d': (0, -200), 'g': (-200, 0), 's': (0, 200), 'b': (200, 0)}
        prims = [L(-200, 0, -60, 0), L(-60, -80, -60, 80), L(-30, -80, -30, 80), L(-30, -60, 0, -60),
                 L(0, -60, 0, -200), L(-30, 60, 0, 60), L(0, 60, 0, 200), L(-30, 0, 200, 0),
                 T('d', 10, -170), T('s', 10, 170), T('g', -190, -20), T('b', 120, -20)]
    else:                      # capacitor: PLUS top, MINUS bottom
        pos = {'PLUS': (0, -200), 'MINUS': (0, 200)}
        prims = [L(0, -200, 0, -20), L(-60, -20, 60, -20), L(-60, 20, 60, 20), L(0, 20, 0, 200), T('+', 20, -70)]
    pins = []
    for i, p in enumerate(ports):
        x, y = pos[p]
        pins.append({"LocalX": x, "LocalY": y, "PortIndex": i, "Name": p})
    json.dump({"FormatVersion": 6, "GridSize": 100, "PortCount": len(ports),
               "Primitives": prims, "Pins": pins}, open(path, 'w'), indent=1)


def write_cell(lib, name, ports, cell_params, sheet, kind, doc):
    d = os.path.join(lib, name)
    os.makedirs(os.path.join(d, 'schematic'), exist_ok=True)
    os.makedirs(os.path.join(d, 'symbol'), exist_ok=True)
    json.dump({"FormatVersion": 1,
               "Parameters": [{"Name": n, "DefaultExpression": v, "Unit": "", "Dimension": "None",
                               "ShowOnSchematic": show} for n, v, show in cell_params],
               "IsTestBench": False, "FlattenForLvs": True,
               "Terminals": [{"Port": i + 1, "Name": p, "LayoutPin": p} for i, p in enumerate(ports)],
               "NumPorts": len(ports)}, open(os.path.join(d, '.ccell'), 'w'), indent=1)
    sheet.write(os.path.join(d, 'schematic', name + '.csch'))
    symbol(os.path.join(d, 'symbol', name + '.csym'), kind, ports)
    open(os.path.join(d, 'README.md'), 'w').write(doc)

# ---------------------------------------------------------------- devices

CORNERS = ('typ', 'bcs', 'wcs')


def corner_vars(cornerlib, prefix, wanted, sections=CORNERS):
    """name -> circuitRF expression selecting the corner's value; wanted: lowercase names."""
    secs = [corner_section(cornerlib, '%s_%s' % (prefix, c)) for c in sections]
    out = {}
    for name in secs[0]:
        if name.lower() not in wanted:
            continue
        v = [s.get(name, secs[0][name]) for s in secs]
        out[name] = v[0] if v[0] == v[1] == v[2] else \
            'corner==1 ? %s : (corner==2 ? %s : %s)' % (v[1], v[2], v[0])
    return out


def device_cell(lib, osdi_dir, lines, cornerlib, corner_prefix, name, user, kind, doc,
                drop=(), instance_extra=()):
    """One PDK subckt holding one compact-model instance plus R/C parasitics."""
    ports, body = subckt(lines, name)
    sub_pars = []
    for l in body:
        if l.lower().startswith('.param'):
            sub_pars += assignments(l[6:])
    sub_names = {n.lower() for n, _ in sub_pars}
    user_l = {u.lower(): u for u in user}

    inst = next(l for l in body if l[0].upper() in 'QN' and not l.lower().startswith('.'))
    toks = inst.split()
    # the instance: name, nets..., model, key=value...
    nets_and_model = [t for t in toks[1:] if '=' not in t]
    model_name, inst_nets = nets_and_model[-1], nets_and_model[:-1]
    inst_pars = assignments(inst.split(model_name, 1)[1])
    mtype, card = model_card(lines, model_name)

    wanted = set()
    for _, v in sub_pars + card + inst_pars:
        wanted |= {w.lower() for w in re.findall(r'[A-Za-z_]\w*', v)}
    cvars = corner_vars(cornerlib, corner_prefix, wanted)

    names = {n.lower(): n for n, _ in sub_pars}
    names.update({n.lower(): n for n in cvars})
    names.update({k: v for k, v in user_l.items()})
    names.update({'corner': 'corner', 't': 'T'})
    tr = lambda e: translate(e, names)

    sheet = Sheet(name)
    terminals(sheet, ports, -1400, -300)

    # VAR: corner multipliers first, then the subckt's own derived parameters
    var = [(n, tr(v)) for n, v in cvars.items()]
    var += [(n, tr(v)) for n, v in sub_pars if n.lower() not in user_l]
    sheet.comp('VAR1', 'Var', -1400, -1400, [par(n, v) for n, v in var])

    osdi = {'npn': 'vbic_1p3_5t.osdi', 'r3_cmc': 'r3_cmc.osdi'}[mtype]
    params = [(k.lower(), tr(v)) for k, v in card if k.lower() not in drop]
    # OSDI names the multiplicity $mfactor; the PDK's netlist calls it m.
    params += [('$mfactor' if k.lower() == 'm' else k.lower(), tr(v))
               for k, v in inst_pars if k.lower() not in drop]
    params += list(instance_extra)
    nets = list(inst_nets)
    therm = nets[-1]                                    # t / dt: the thermal node
    verilog_a(sheet, 0, 0, os.path.join(osdi_dir, osdi), nets, params)

    x = 800
    for l in body:                                     # the parasitics around the model
        t = l.split()
        if t[0][0].upper() in 'RC' and not l.startswith('.'):
            kv = dict(assignments(l))
            val = kv.get('R') or kv.get('r') or kv.get('C') or kv.get('c') or t[3]
            sym = 'Resistor' if t[0][0].upper() == 'R' else 'Capacitor'
            sheet.two_pin(t[0], sym, x, 0, par(t[0][0].upper(), tr(val), True), t[1], t[2])
            x += 400
    if not any(l.split()[0][0].upper() == 'R' and therm in l.split()[1:3] for l in body):
        sheet.two_pin('Rt', 'Resistor', x, 0, par('R', '1e9', True), therm, '0')   # PDK: Rt t 0 1e9

    cell_params = [(user_l[u.lower()], dict((n.lower(), v) for n, v in sub_pars).get(u.lower(), d), True)
                   for u, d in user.items()]
    write_cell(lib, name, ports, cell_params, sheet, kind, doc)
    return ports


def cap_cell(lib, lines, cornerlib, name='cap_cmim'):
    ports, body = subckt(lines, name)
    sub = []
    for l in body:
        if l.lower().startswith('.param'):
            sub += assignments(l[6:])
    _, card = model_card(lines, 'cmim_core')
    card = {k.lower(): v for k, v in card}
    cvars = corner_vars(cornerlib, 'cap', {'cap_carea'})
    names = {'w': 'w', 'l': 'l', 'cap_carea': 'cap_carea', 't': 'T', 'corner': 'corner'}
    tr = lambda e: translate(e, names)
    sheet = Sheet(name)
    terminals(sheet, ports, -1400, -300)
    # ngspice C model: C = CJ*W*L + CJSW*2*(W+L) with W, L in um here (the PDK passes l/sf,
    # sf=1e-6), times the temperature polynomial around TNOM.
    dt = '(T-%s)' % card['tnom']
    var = [('cap_carea', tr(cvars['cap_carea'])),
           ('Cmim', '(cap_carea*(w*1e6)*(l*1e6) + %s*2*(w*1e6+l*1e6))*(1 + %s*%s + %s*%s^2)'
            % (tr(card['cjsw']), tr(card['tc1']), dt, tr(card['tc2']), dt))]
    sheet.comp('VAR1', 'Var', -1400, -1400, [par(n, v) for n, v in var])
    r1 = next(l for l in body if l.upper().startswith('R1'))
    sheet.two_pin('R1', 'Resistor', 0, 0, par('R', tr(dict(assignments(r1))['r']), True), ports[0], 'n1')
    sheet.two_pin('C1', 'Capacitor', 400, 0, par('C', 'Cmim', True), 'n1', ports[1])
    defaults = dict(sub)
    write_cell(lib, name, ports, [('w', tr(defaults['w']), True), ('l', tr(defaults['l']), True),
                                  ('corner', '0', False), ('T', '27', False)], sheet, 'cap',
               DOCS['cap_cmim'])


# The PDK's MOS subckt (rfmode 0, as = 0) computes the junction areas and perimeters from w, ng, z1 and z2,
# one formula for odd ng and one for even; circuitRF's expressions have no floor, so cos(pi*ng) tells them apart.
WG, ODD = 'max(w/ng,wmin)', 'cos(pi*ng)<0'
MOS_GEO = [('asx', f'{ODD}?{WG}*(z1+((ng-1)/2)*z2):{WG}*(2*z1+max(0,(ng-2)/2)*z2)'),
           ('adx', f'{ODD}?{WG}*(z1+((ng-1)/2)*z2):{WG}*z2/2*ng'),
           ('psx', f'{ODD}?2*({WG}*((ng-1)/2+1)+z1+(ng-1)/2*z2):2*({WG}*(2+max(ng-2,0)/2)+2*z1+max(ng-2,0)/2*z2)'),
           ('pdx', f'{ODD}?2*({WG}*((ng-1)/2+1)+z1+(ng-1)/2*z2):({WG}+z2)*ng')]


def mos_cell(lib, osdi_dir, mod, parm, cornerlib, name):
    """A PDK MOSFET (sg13g2_mos*_mod.lib): its PSP 103 card on the PDK's psp103.osdi, the subckt's geometry."""
    hdr = next(l for l in mod if l.lower().startswith('.subckt %s ' % name))
    ports, sp = [t for t in hdr.split()[2:] if '=' not in t], dict(assignments(hdr))
    _, card = model_card(parm, name.replace('sg13_', 'sg13g2_') + '_psp')
    wanted = {w.lower() for _, v in card for w in re.findall(r'[A-Za-z_]\w*', v)}
    cvars = corner_vars(cornerlib, 'mos', wanted, ('tt', 'ff', 'ss'))
    names = {n.lower(): v for l in mod if l.lower().startswith('.param') for n, v in assignments(l[6:])}
    names.update({n.lower(): n for n in list(cvars) + ['w', 'l', 'ng', 'm', 'pre_layout', 'corner']})
    tr = lambda e: translate(e, names)
    sheet = Sheet(name)
    terminals(sheet, ports, -1400, -300)
    var = [(n, tr(v)) for n, v in cvars.items()] + [(n, tr(sp[n])) for n in ('z1', 'z2', 'wmin')] + MOS_GEO
    sheet.comp('VAR1', 'Var', -1400, -1400, [par(n, v) for n, v in var])
    # circuitRF names PSP's parameters as the module does, in capitals; level only picks ngspice's model.
    params = [('Model', 'PSP103VA')] + [(k.upper(), tr(v)) for k, v in card if k.lower() != 'level']
    params += [('W', 'w'), ('L', 'l'), ('NF', 'ng'), ('MULT', 'm'), ('AS', 'asx'), ('AD', 'adx'), ('PS', 'psx'),
               ('PD', 'pdx'), ('DTA', 'trise'), ('NGCON', '2'), ('DELVTO', '0'), ('FACTUO', '1'), ('Temp', 'T')]
    verilog_a(sheet, 0, 0, os.path.join(osdi_dir, 'psp103.osdi'), ports, params)
    user = [('w', tr(sp['w']), True), ('l', tr(sp['l']), True), ('ng', sp['ng'], True), ('m', sp['m'], False),
            ('corner', '0', False), ('T', '27', False), ('trise', sp['trise'], False),
            ('pre_layout', sp['pre_layout'], False)]
    write_cell(lib, name, ports, user, sheet, 'mos', MOS_DOC.format(name=name))


MOS_DOC = """# {name}

IHP SG13G2 {name} as in the PDK (`sg13g2_mos*_mod.lib`, rfmode 0): PSP 103.6
(the PDK's psp103.osdi) with the PDK's card and corner factors, source and
drain junctions from w, ng and the subckt's z1, z2.

| Parameter | Meaning |
|---|---|
| w, l | total gate width and length, m |
| ng | gate fingers |
| m | parallel devices |
| corner | 0 tt, 1 ff, 2 ss (cornerMOS*.lib) |
| T | ambient temperature, degC (PDK default 27) |
| trise | temperature offset, K |
| pre_layout | 1 pre-layout (PDK default), 0 post-layout |

Terminals: d, g, s, b. Generated by ihp2crf.py; do not edit, regenerate.
"""
HBT_DOC = """# {name}

IHP SG13G2 {name} as in the PDK (`sg13g2_hbt_mod.lib`): VBIC 1.3 (OSDI,
five terminals), every model parameter the PDK's own expression of the cell
parameters, substrate network and thermal node as in the PDK subcircuit.

| Parameter | Meaning |
|---|---|
| Nx | number of emitters |{le}
| corner | 0 typ, 1 bcs, 2 wcs (cornerHBT.lib) |
| T | ambient temperature, degC (PDK default 27) |
| dtemp | device temperature offset, K |
| selft | 1 self-heating (PDK default), 0 off |

Terminals: c, b, e, bn (substrate). Generated by ihp2crf.py; do not edit,
regenerate.
"""
RES_DOC = """# {name}

IHP SG13G2 {name} as in the PDK (`resistors_mod.lib`): CMC R3 (OSDI), every
parameter the PDK's own expression of w, l{b} and the corner.

| Parameter | Meaning |
|---|---|
| w, l | drawn width and length, m |{bdoc}
| m | parallel devices |
| corner | 0 typ, 1 bcs, 2 wcs (cornerRES.lib) |
| T | ambient temperature, degC (PDK default 27) |
| trise | temperature offset, K |

Terminals: 1, 2, bn (body). Generated by ihp2crf.py; do not edit, regenerate.
"""
DOCS = {'cap_cmim': """# cap_cmim

IHP SG13G2 MIM capacitor as in the PDK (`capacitors_mod.lib`): 55 mOhm in
series with C = cap_carea*W*L + 40 aF/um * perimeter (W, L in um), with the
model's temperature coefficients around 27 degC.

| Parameter | Meaning |
|---|---|
| w, l | plate width and length, m |
| corner | 0 typ, 1 bcs, 2 wcs (cornerCAP.lib) |
| T | temperature, degC |

Terminals: PLUS (top plate), MINUS. Plate parasitics come from extraction,
as in the PDK. Generated by ihp2crf.py; do not edit, regenerate.
"""}


# The cross-section of SG13G2_os_process_spec.pdf (Rev. 1.2, Fig. 1.1.1 and table 2.16), top down, in um: what the
# ITF does not give (passivation, the gaps between metals, the MIM, the silicon). Conductor thicknesses and
# resistances, and the vias, come from the ITF.
SPEC_PASSIVATION = (0.4, 6.6, 1.5)          # TPASS2 SiN, its eR; TPASS1 oxide over TopMetal2
SPEC_GAP = {('TopMetal2', 'TopMetal1'): 2.8, ('TopMetal1', 'Metal5'): 0.85, ('Metal5', 'Metal4'): 0.54,
            ('Metal4', 'Metal3'): 0.54, ('Metal3', 'Metal2'): 0.54, ('Metal2', 'Metal1'): 0.54}
SPEC_ILD0 = (0.64, 0.62)                    # Metal1 to Activ: 640 nm of oxide and nitride, modelled as 620 nm at eR 4.1
SPEC_MIM = (0.04, 0.15, 1.5e-3)             # TISMIM dielectric, TMIMTOP plate, CMIMA 1.5 fF/um2 (F/m2), on Metal5
SPEC_STI = 0.4                              # TSTI, the Activ slab
SPEC_SILICON = ((3.75, 20.0), (750.0, 50.0))   # EPI and bulk: thickness um, resistivity Ohm cm
EPS_OX = 4.1
# Neither the ITF nor the process specification states these two; they are the values IHP's EM workflow uses.
MIM_PLATE_SIGMA, VMIM_SIGMA = 5.0e5, 2.191e6


def read_itf(path):
    """CONDUCTOR name -> (thickness um, RPSQ ohm/sq); VIA name -> (from, to, area um2, ohm per via)."""
    text = open(path).read()
    kv = lambda body: dict(re.findall(r'(\w+)=([\w.+-]+)', body))
    conds = {n: (float(p['THICKNESS']), float(p['RPSQ']))
             for n, p in ((m[1], kv(m[2])) for m in re.finditer(r'^CONDUCTOR\s+(\w+)\s*\{([^}]*)\}', text, re.M))}
    vias = {n: (p['FROM'], p['TO'], float(p['AREA']), float(p['RPV']))
            for n, p in ((m[1], kv(m[2])) for m in re.finditer(r'^VIA\s+(\w+)\s*\{([^}]*)\}', text, re.M))}
    return conds, vias


def make_tech(pdk, path):
    """IHP SG13G2 technology: KLayout's layer table, and an EM stackup from the PDK's Apache-2.0 sources: the ITF
    (libs.tech/parasitics/itf/sg13g2_typ.itf) for the metals and vias, the process specification for the rest."""
    import xml.etree.ElementTree as ET
    layers, seen, gds = [], set(), {}
    for i, p in enumerate(ET.parse(os.path.join(pdk, 'libs.tech/klayout/tech/sg13g2.lyp')).getroot().iter('properties')):
        src, name = (p.findtext('source') or '').strip(), (p.findtext('name') or '').strip()
        m = re.match(r'(\d+)/(\d+)', src)
        if not m or (int(m[1]), int(m[2])) in seen:
            continue
        seen.add((int(m[1]), int(m[2])))
        gds.setdefault(name, {"Layer": int(m[1]), "Datatype": int(m[2])})
        c = (p.findtext('fill-color') or '#808080').lstrip('#')
        layers.append({"Key": {"Layer": int(m[1]), "Datatype": int(m[2])}, "Name": name,
                       "Color": {"r": int(c[0:2], 16), "g": int(c[2:4], 16), "b": int(c[4:6], 16), "a": 255},
                       "FillOpacity": 0.35, "ZOrder": i, "Visible": (p.findtext('visible') or 'true') == 'true',
                       "Selectable": True, "Purpose": name.split('.')[-1] if '.' in name else 'drawing'})

    conds, vias = read_itf(os.path.join(pdk, 'libs.tech/parasitics/itf/sg13g2_typ.itf'))
    dbu = lambda um: int(round(um * 1000))                         # 1 DBU = 1 nm

    def dielectric(name, t_um, epsr, sigma=0.0):
        return {"Kind": "Dielectric", "Name": name, "ThicknessDbu": dbu(t_um), "Epsr": round(epsr, 4), "TanD": 0.0,
                "Mur": 1, "SigmaSm": sigma, "DrawingLayers": [], "IsGroundReference": False}

    def conductor(name, t_um, sigma, layer=None, ground=False):
        return {"Kind": "Conductor", "Name": name, "ThicknessDbu": dbu(t_um), "Epsr": 1, "TanD": 0, "Mur": 1,
                "SigmaSm": float('%.4g' % sigma), "DrawingLayers": [gds[layer + '.drawing']] if layer else [],
                "IsGroundReference": ground}

    def metal(name):                                               # sigma = 1 / (RPSQ * t)
        t, rpsq = conds[name]
        return conductor(name, t, 1 / (rpsq * t * 1e-6), name)

    t_sin, eps_sin, t_pass_ox = SPEC_PASSIVATION
    t_mim, t_plate, c_mim = SPEC_MIM
    eps_mim = c_mim * t_mim * 1e-6 / 8.8541878128e-12             # the permittivity that gives CMIMA at TISMIM
    stack = [dielectric('Passive', t_sin, eps_sin), dielectric('SiO2 1', t_pass_ox, EPS_OX), metal('TopMetal2'),
             dielectric('SiO2 2', SPEC_GAP['TopMetal2', 'TopMetal1'], EPS_OX), metal('TopMetal1'),
             dielectric('SiO2 3', SPEC_GAP['TopMetal1', 'Metal5'] - t_plate - t_mim, EPS_OX),
             conductor('MIM', t_plate, MIM_PLATE_SIGMA, 'MIM'), dielectric('MIM dielectric', t_mim, eps_mim)]
    lower = ['Metal5', 'Metal4', 'Metal3', 'Metal2', 'Metal1']
    for k, name in enumerate(lower):
        stack.append(metal(name))
        if k + 1 < len(lower):
            stack.append(dielectric('SiO2 %d' % (k + 4), SPEC_GAP[name, lower[k + 1]], EPS_OX))
    t_ild0, t_eff = SPEC_ILD0
    stack.append(dielectric('ILD0', t_ild0, EPS_OX * t_ild0 / t_eff))
    t_act, rpsq_act = conds['Activ']
    stack.append(conductor('Activ', SPEC_STI, 1 / (rpsq_act * t_act * 1e-6), 'Activ'))
    for name, (t, rho) in zip(('EPI', 'Substrate'), SPEC_SILICON):
        stack.append(dielectric(name, t, 11.9, 100.0 / rho))       # Ohm cm -> S/m
    stack.append(conductor('Backside', 1.0, 5.8e7, ground=True))

    # A via's sigma = h / (RPV * AREA), h the gap it crosses. The ITF calls the contact to Activ ContIntActiv.
    thick = {l['Name']: l['ThicknessDbu'] / 1000 for l in stack}
    order = [l['Name'] for l in stack]
    def gap(lo, hi):                                               # from the top of lo to the bottom of hi
        return sum(thick[n] for n in order[order.index(hi) + 1:order.index(lo)])
    def via(name, layer, lo, hi, sigma):
        return {"Kind": "Via", "Name": name, "ThicknessDbu": 0, "Epsr": 1, "TanD": 0, "Mur": 1,
                "SigmaSm": float('%.4g' % sigma), "DrawingLayers": [gds[layer + '.drawing']],
                "IsGroundReference": False, "Fill": "Solid", "SpanFromLayer": lo, "SpanToLayer": hi}
    for itf_name, name in (('TopVia2', 'TopVia2'), ('TopVia1', 'TopVia1'), ('Via4', 'Via4'), ('Via3', 'Via3'),
                           ('Via2', 'Via2'), ('Via1', 'Via1'), ('ContIntActiv', 'Cont')):
        lo, hi, area, rpv = vias[itf_name]
        stack.append(via(name, name, lo, hi, gap(lo, hi) * 1e-6 / (rpv * area * 1e-12)))
    stack.append(via('Vmim', 'Vmim', 'MIM', 'TopMetal1', VMIM_SIGMA))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"FormatVersion": 1, "Name": "IHP SG13G2 (from the PDK's ITF and process specification)",
               "DefaultDisplayUnit": "Um", "DefaultSnapDbu": 5, "Layers": layers,
               "Stackup": {"Top": "Open", "Bottom": "Ground", "Layers": stack}, "DrcRules": []},
              open(path, 'w'), indent=1)


KIT_DOC = """# IHP SG13G2 kit for circuitRF

Generated from the IHP SG13G2 PDK (commit {commit}) by `ihp2crf.py`; checked
against the PDK's own models in ngspice and Xyce by `validate_ihp_kit.py`.
Both are in `generator/` of github.com/aissus/circuitRF-IHP-SG13G2-PDK, the
repository this kit is built in (`./kit.sh generator/build.sh` redoes all of
it). Do not edit; regenerate.

Start a project on it:

    generator/circuitrf-ihp-workspace my_project      # then open my_project in circuitRF

The workspace references this folder as a library (Workspace > Libraries >
IHP_SG13G2) and gets its own copy of the technology. It also imports the IHP
Open PDK itself (circuitRF 1.7.5 or newer), whose own parts simulate as
imported; the HBTs among them run on this kit's VBIC 1.3, which the workspace
declares to stand in for ngspice's built-in VBIC. `VALIDATION` checks those
parts too (the rows marked pdk://).

| Cell | Device | Parameters |
|---|---|---|
| npn13G2 | HBT, high fT | Nx, corner, T, dtemp, selft |
| npn13G2l | HBT, long emitter | Nx, le, corner, T, dtemp, selft |
| npn13G2v | HBT, high breakdown | Nx, le, corner, T, dtemp, selft |
| rsil | silicided poly resistor | w, l, m, corner, T, trise |
| rppd | p+ poly resistor | w, l, b, m, corner, T, trise |
| rhigh | high-ohmic poly resistor | w, l, b, m, corner, T, trise |
| cap_cmim | MIM capacitor | w, l, corner, T |
| sg13_lv_nmos, sg13_lv_pmos | 1.2 V MOSFETs | w, l, ng, m, corner, T, trise, pre_layout |
| sg13_hv_nmos, sg13_hv_pmos | 3.3 V MOSFETs | w, l, ng, m, corner, T, trise, pre_layout |

corner: 0 typ, 1 bcs, 2 wcs (MOSFETs: 0 tt, 1 ff, 2 ss). T in degC (27 is the PDK's nominal; circuitRF's
own default would be 26.85). Lengths in metres, as in the PDK.

Symbols are IHP's Qucs-S ones (qucs2csym.py, from the PDK's qucs-s/user_lib).

**harmonicaRF** (interactive harmonic load-pull, Tools > harmonicaRF in
circuitRF) takes a single compiled device, not a subcircuit cell, so the HBTs
are also compiled whole: `models/osdi/npn13G2.osdi`, `npn13G2l.osdi` and
`npn13G2v.osdi` are VBIC 1.3 as base, collector, emitter (what harmonicaRF
connects as gate, drain, source), thermal node internal, the PDK substrate
network built in, and every VBIC parameter set inside from the PDK's own
expressions. Their only parameters are Nx (and le on npn13G2l/v), corner and
temp. Ready-to-pull documents are in the repository's examples/harmonica; make
others with `generator/harmonica_ihp.py charm <out> --device npn13G2v --nx 4 ...`.

**Layout.** IHP's own KLayout PCells (`sg13g2_pycell_lib`: HBTs, MOS,
resistors, MIM, inductors, diodes, ESD, pads, seal ring, ...) come with the
PDK import: circuitRF declares them in the workspace's `ihp-sg13g2-pcells/`
and draws them through its CNI bridge. `PCELLS` lists each one, drawn by
circuitRF and compared with KLayout's own drawing. circuitRF runs the PDK's
scripts once you allow them (it asks; headless, `--trust-kit <that folder>`).
The PDK declares most parameters as text: write lengths as `0.9u` or `9e-07`
and counts such as `ng` and `b` as `2`. A bare number in a text field is
ignored, and the cell keeps its default. circuitRF links a PCell to the PDK's
imported parts, not to library cells such as this kit's, so a kit cell has no
layout view: place the PCell with the cell's values, or design with the
imported part.

`tech/IHP_SG13G2.ctech`: all 378 KLayout layers with their GDS numbers, and
an EM stackup from the PDK's ITF (metal thickness and sheet resistance, vias)
and process specification (passivation, the oxide between the metals, the MIM,
EPI 3.75 um at 20 Ohm cm, a 750 um wafer at 50 Ohm cm, ground at the backside).
A workspace gets its own copy, so a thinned die is a change to that copy's
Substrate row. No DRC rules: use KLayout's IHP decks.

Accuracy against the PDK (validate_ihp_kit.py): resistors and MIM capacitor
within 0.1 %; HBT currents within 0.1 % at moderate current, up to ~1.5 % at
high power with self-heating (the VBIC 1.3 source has a temperature-dependent
rth, ngspice's built-in VBIC does not), and a few nA off at sub-uA base
currents. Harmonic balance, npn13G2 at 10 GHz into compression: within
0.015 dB of Xyce, as a kit cell and as the harmonicaRF DUT.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pdk', default=os.environ.get('PDKPATH'))
    # As the cells name their models. circuitRF resolves a relative reference in a library cell against the
    # library's root, the folder holding its .cws (written below), so the kit can be moved or copied whole.
    ap.add_argument('--osdi', default='models/osdi')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    m = os.path.join(a.pdk, 'libs.tech', 'ngspice', 'models')
    os.makedirs(a.out, exist_ok=True)

    hbt = logical_lines(read(os.path.join(m, 'sg13g2_hbt_mod.lib')))
    chbt = logical_lines(read(os.path.join(m, 'cornerHBT.lib')))
    for name in ('npn13G2', 'npn13G2l', 'npn13G2v'):
        _, body = subckt(hbt, name)
        sp = dict((k.lower(), v) for l in body if l.lower().startswith('.param') for k, v in assignments(l[6:]))
        user = {'Nx': sp['nx'], 'corner': '0', 'T': '27', 'dtemp': sp.get('dtemp', '0'), 'selft': sp.get('selft', '1')}
        if name != 'npn13G2':
            user['le'] = sp['le']
        device_cell(a.out, a.osdi, hbt, chbt, 'hbt', name, user, 'npn',
                    HBT_DOC.format(name=name, le='\n| le | emitter length, m |' if 'le' in user else ''),
                    drop={'level', 'vbe_max', 'vbc_max', 'vce_max', 'dtemp', 'm'},
                    instance_extra=[('Temp', 'T+dtemp')])

    res = logical_lines(read(os.path.join(m, 'resistors_mod.lib')))
    res_mm = logical_lines(read(os.path.join(m, 'resistors_mod_mismatch.lib')))
    cres = logical_lines(read(os.path.join(m, 'cornerRES.lib')))
    for name in ('rsil', 'rppd', 'rhigh'):
        src = res if any(l.lower().startswith('.subckt %s ' % name) for l in res) else res_mm
        _, body = subckt(src, name)
        sp = dict((k.lower(), v) for l in body if l.lower().startswith('.param') for k, v in assignments(l[6:]))
        user = {'w': sp['w'], 'l': sp['l'], 'm': sp.get('m', '1'), 'corner': '0', 'T': '27', 'trise': sp.get('trise', '0')}
        if 'b' in sp:
            user['b'] = sp['b']
        device_cell(a.out, a.osdi, src, cres, 'res', name, user, 'res',
                    RES_DOC.format(name=name, b=', b' if 'b' in user else '',
                                   bdoc='\n| b | number of bends |' if 'b' in user else ''),
                    drop={'level'}, instance_extra=[('Temp', 'T')])

    cap = logical_lines(read(os.path.join(m, 'capacitors_mod.lib')))
    cap_cell(a.out, cap, logical_lines(read(os.path.join(m, 'cornerCAP.lib'))))
    for v in ('lv', 'hv'):
        lib = [logical_lines(read(os.path.join(m, f))) for f in
               ('sg13g2_mos%s_mod.lib' % v, 'sg13g2_mos%s_parm.lib' % v, 'cornerMOS%s.lib' % v)]
        for t in ('nmos', 'pmos'):
            mos_cell(a.out, a.osdi, *lib, 'sg13_%s_%s' % (v, t))
    make_tech(a.pdk, os.path.join(a.out, 'tech', 'IHP_SG13G2.ctech'))
    commit = open(os.path.join(a.pdk, 'COMMIT')).read().strip() if os.path.exists(os.path.join(a.pdk, 'COMMIT')) else '?'
    open(os.path.join(a.out, 'README.md'), 'w').write(KIT_DOC.format(commit=commit))
    # The kit is a library workspace: a workspace's LibraryRefs names it, and its .cws makes it the root its
    # cells' relative model paths resolve against.
    json.dump({'FormatVersion': 2, 'LibraryRefs': [], 'KnownFiles': [], 'DefaultTechRef': 'tech/IHP_SG13G2.ctech'},
              open(os.path.join(a.out, '.cws'), 'w'), indent=2)
    print('cells and tech/IHP_SG13G2.ctech written to', a.out)


if __name__ == '__main__':
    main()
