"""IHP SG13G2's own KLayout PCells (sg13g2_pycell_lib) as circuitRF parametric cells.

build.sh copies this file into the kit as pcells/kit_entry.py, beside the pcell-generators.json that
names it. circuitRF runs it, with its own circuitrf_pcell and cni packages on the path, and
cni.bridge.register_kit turns every cell of the PDK's package into a generator of the same name
(npn13G2, rsil, cmim, ...), parameters as the PDK declares them. Nothing here draws.

The PDK is found at run time, so the kit names no machine path: $PDKPATH (IIC-OSIC-TOOLS sets it),
else $PDK_ROOT/ihp-sg13g2. Without it the kit offers no PCells and says so; its cells still simulate.
"""
import os
import sys
import types

import circuitrf_pcell as crf
import cni
import cni.dlo as dlo
from cni.bridge import register_kit

pdk = os.environ.get('PDKPATH') or os.path.join(os.environ.get('PDK_ROOT', '/'), 'ihp-sg13g2')
lib = os.path.join(pdk, 'libs.tech', 'klayout', 'python')

if os.path.isdir(os.path.join(lib, 'sg13g2_pycell_lib')):
    sys.path.insert(0, lib)
    # Names the PDK's cells import that circuitRF 1.7.3's cni does not have. Aliases of its own
    # classes and a placeholder constant, no geometry: device_base_code (every resistor, MIM, MOS,
    # inductor and antenna) imports cni.rect and cni.text, cmomi/cmomf pass USE_DEFAULT to a
    # RangeConstraint, and chipText reads a polygon's points back.
    for name, cls in (('rect', 'Rect'), ('text', 'Text')):
        if not hasattr(cni, name):
            m = types.ModuleType('cni.' + name)
            setattr(m, cls, getattr(dlo, cls))
            sys.modules['cni.' + name] = m
            setattr(cni, name, m)
    if not hasattr(dlo, 'USE_DEFAULT'):
        dlo.USE_DEFAULT = None
        dlo.__all__.append('USE_DEFAULT')
    if not hasattr(dlo.Polygon, 'getPoints'):
        dlo.Polygon.getPoints = lambda self, *_: self.points
    # Three behaviours of the API the cells are written against (pycell4klayout-api) that circuitRF
    # 1.7.3's cni does differently; each checked against KLayout's own drawing (check_ihp_pcells.py).
    # 1. The operands stay drawn; a cell deletes the ones it does not want (npn13G2L/V keep their
    #    Activ.mask rectangles this way).
    # 2. A result fed into another boolean keeps its holes. The host unions the rings it is given, so
    #    a polygon with holes goes in as hole-free slabs, cut at its holes' y coordinates (rfcmim's
    #    guard ring otherwise comes out as a filled square of Activ and Metal1).
    import cni.geo as geo
    clip, rings_of = geo._clip, geo._rings_of

    def _clip(rule, subject, other):
        ctx = dlo.current_context()
        keep = [f for f in geo._as_figures(subject) + geo._as_figures(other) if ctx and f in ctx.figures]
        result = clip(rule, subject, other)
        ctx.figures += [f for f in keep if f not in ctx.figures]
        return result

    def _rings_of(fig, dbu):
        if not (isinstance(fig, dlo.Polygon) and fig.holes):
            return rings_of(fig, dbu)
        d = lambda v: crf.dbu(v * dbu)
        outer = [(d(p.x), d(p.y)) for p in fig.points]
        holes = [[(d(p.x), d(p.y)) for p in h] for h in fig.holes]
        x0, x1 = min(x for x, _ in outer) - 1, max(x for x, _ in outer) + 1
        y0, y1 = min(y for _, y in outer) - 1, max(y for _, y in outer) + 1
        cuts = [y0] + sorted({y for h in holes for _, y in h}) + [y1]
        box = lambda a, b: [(x0, a), (x1, a), (x1, b), (x0, b)]
        return [p.outer for lo, hi in zip(cuts, cuts[1:])
                for p in crf.clip('not', [outer], holes + [box(y0 - 1, lo), box(hi, y1 + 1)])]

    geo._clip, geo._rings_of = _clip, _rings_of
    # 3. A copy keeps the tags a cell sets on a figure (fig.col = True), as the cell's own figures
    #    do: the HBTs size their C/B/E pins from the tagged figures, copies made for Nx > 1 included.
    for cls in (dlo.Rect, dlo.Polygon):
        def clone(self, _clone=cls.clone):
            new = _clone(self)
            for k, v in vars(self).items():
                vars(new).setdefault(k, v)
            return new
        cls.clone = clone
    # The package's initialiser registers the cells with KLayout. circuitRF registers them itself, so
    # KLayout's module is stood in for even where it is installed (IIC-OSIC-TOOLS has it on
    # PYTHONPATH): the real one refuses circuitRF's cell wrapper, and no cell draws through it.
    from cni.hostglue import _Inert
    pya = types.ModuleType('pya')
    pya.__getattr__ = lambda name: _Inert('pya.' + name)
    sys.modules['pya'] = pya

    # The package's shared bases, which the bridge cannot tell from devices: they draw nothing.
    bases = {'DeviceBase', 'ResistorBase', 'rfmosfet_base', 'inductors'}
    found = register_kit('sg13g2_pycell_lib.ihp', registry=crf.Registry())
    result = register_kit('sg13g2_pycell_lib.ihp', only=[i for i in found.ids if i not in bases])
    for problem in result.problems:
        if not problem.startswith(tuple(bases)):
            print(problem, file=sys.stderr)
else:
    print('IHP SG13G2 PCells: no PDK at %s; set PDKPATH to the IHP SG13G2 PDK to draw its cells' % pdk,
          file=sys.stderr)

crf.run()
