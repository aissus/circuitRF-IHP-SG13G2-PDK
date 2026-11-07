"""The example inductor, drawn by IHP's own inductor2 PCell and written as circuitRF layouts:

    ./kit.sh klayout -b -r examples/inductor/inductor_from_pcell.py

Two turns of 5.4 um TopMetal2 at 4.1 um spacing, at the smallest centre opening the PCell allows for them
(62.63 um; 92.5 um across). Only the layers the EM stackup carries are kept: TopMetal2, TopMetal1 and TopVia2.
Added for the EM setups: a port label on each of the PCell's two TopMetal1 terminals, and a 20 um Metal1 ring
22 um clear of the coil, under the terminals, which the 3D solvers' ports return to (Ports3D): layout/inductor.clay.

layout/inductor_mom.clay is the same coil for circuitRF's planar MoM, measured differentially: a TopMetal1 bar
joins the two terminals and one internal delta-gap port cuts the bar in its middle. The planar kernel returns
an edge port to the stackup's ground (here the backside, 750 um down) and de-embeds it on a feed line that has
to be clear of other metal by several substrate heights, which two terminals 9.5 um apart can never be; a
delta gap needs neither. The bar adds a few pH of its own.
"""
import json, os, sys, importlib
import pya

HERE = os.path.dirname(os.path.abspath(__file__))
k = os.path.join(os.environ['PDKPATH'], 'libs.tech', 'klayout', 'python')
sys.path += [k, os.path.join(k, 'pycell4klayout-api', 'source', 'python')]
importlib.import_module('sg13g2_pycell_lib')          # what the PDK's KLayout autorun does: registers SG13_dev

ly = pya.Layout()
ly.dbu = 0.001                                        # 1 nm, circuitRF's DBU too
ly.technology_name = 'sg13g2'
cell = ly.create_cell('inductor2', 'SG13_dev', {'w': '5.4u', 's': '4.1u', 'd': '62.63u', 'nr_r': 2})


def poly(layer, pts):
    return {'$type': 'Poly', 'Layer': {'Layer': layer[0], 'Datatype': layer[1]},
            'Xy': [v for p in pts for v in (p.x, p.y)]}


coil = []
for layer in ((134, 0), (126, 0), (133, 0)):          # TopMetal2, TopMetal1, TopVia2
    for p in pya.Region(cell.begin_shapes_rec(ly.layer(*layer))).merged().each():
        assert p.holes() == 0, 'a coil polygon with a hole'
        coil.append(poly(layer, p.each_point_hull()))

pins = sorted((p.bbox() for p in pya.Region(cell.begin_shapes_rec(ly.layer(126, 2))).each()),
              key=lambda b: b.center().x)
lead_end = min(b.bottom for b in pins)
ports = [{'$type': 'Label', 'Layer': {'Layer': 126, 'Datatype': 0}, 'X': b.center().x, 'Y': lead_end,
          'Text': str(n), 'Height': 4000, 'IsPort': True, 'PortDirection': 'R90'}
         for n, b in enumerate(pins, 1)]

box = pya.Region(cell.begin_shapes_rec(ly.layer(134, 0))).bbox()
outer, inner = box.enlarged(42000, 42000), box.enlarged(22000, 22000)
assert outer.bottom < lead_end < inner.bottom, 'the terminals must lie over the ring'
corners = lambda b: [pya.Point(b.left, b.bottom), pya.Point(b.right, b.bottom),
                     pya.Point(b.right, b.top), pya.Point(b.left, b.top)]
ring = dict(poly((8, 0), corners(outer)), Holes=[[v for p in corners(inner) for v in (p.x, p.y)]])

def write(name, shapes):
    json.dump({'FormatVersion': 1, 'DbuPerMicron': 1000, 'DisplayUnit': 'Um', 'SnapDbu': 0, 'AngleMode': 'AnyAngle',
               'TechRef': '../../tech/IHP_SG13G2.ctech', 'Shapes': shapes, 'Instances': []},
              open(os.path.join(HERE, 'layout', name), 'w'), indent=1)


write('inductor.clay', coil + [ring] + ports)

w = pins[0].width()                                   # the bar is as wide as a terminal, below both
bar = pya.Box(pins[0].left, lead_end - w, pins[-1].right, lead_end)
gap = {'$type': 'Label', 'Layer': {'Layer': 126, 'Datatype': 0}, 'X': bar.center().x, 'Y': bar.center().y,
       'Text': '1', 'Height': 4000, 'IsPort': True, 'PortDirection': 'R0', 'PortKind': 'InternalDeltaGap'}
write('inductor_mom.clay', coil + [poly((126, 0), corners(bar)), gap])
print('coil %.2f x %.2f um, ports at x = %s um' % (box.width() / 1000, box.height() / 1000,
                                                   ', '.join('%.3f' % (b.center().x / 1000) for b in pins)))
