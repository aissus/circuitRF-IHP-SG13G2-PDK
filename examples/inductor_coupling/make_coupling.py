#!/usr/bin/env python3
"""Writes this example's cells, layouts and EM setups (coordinates in um). Inside the image, in this folder:

    python3 make_coupling.py

  IND_BIG    IHP inductor2 PCell, 2 turns, w 5.4 um, s 4.1 um, d 62.63 um (the kit example's coil, 92.5 um across).
  IND_SMALL  IHP inductor2 PCell, 2 turns, w 4 um, s 2.1 um, d 35 um (62.6 um across).
             Each: layout = the PCell alone, a drawn port on each lead (its own EM run, ind_big / ind_small);
             schematic = that run's 2-port between pins LA and LB: the model a cut puts back.
  PAIR       L1 (big) and L2 (small), 75 um apart coil edge to coil edge, in a TopMetal1 ground plane that clears
             each coil's IND keep-out; 30 um TopMetal1 feeds on the four leads with drawn ports 1-4, and port 5 on
             the plane's edge (the tie). Setups: pair_B (both coils in the EM), pair_A (both cut by name).
The writers, the coil cells and the plane are shared with hbt_core_matching (../blackbox_common/blackbox.py).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'blackbox_common'))
from blackbox import *          # noqa: F401,F403

ws(HERE)
coil_cells()
ccell('PAIR')
FEED = 30.0
sh = [PLANE]
for k, (ref, x0) in enumerate(((BIG, 0.0), (SMALL, XS))):
    for j, side in enumerate((-1, 1)):
        x, w = lead(ref, x0, side)
        sh += [rect(TM1, x - w / 2, -1, x + w / 2, -1 - FEED),
               port(str(2 * k + j + 1), x, -1 - FEED, 'R90', TM1, f'P{2 * k + j + 1}')]
sh.append(port('5', TIE_X, TIE_Y, 'R0', TM1))
clay('PAIR', sh, [inst(BIG, 0, 0, 'L1'), inst(SMALL, XS, 0, 'L2')])
s = Sheet('PAIR')
for k, (n, x) in enumerate((('a1', -1000), ('b1', 1000), ('a2', -1000), ('b2', 1000))):
    term(s, f'P{k + 1}', k + 1, x, 500 + 1500 * (k // 2), n)
coil(s, 'L1', 'IND_BIG', 0, 0, 'a1', 'b1')
coil(s, 'L2', 'IND_SMALL', 0, 1500, 'a2', 'b2')
write_sheet(s, 'PAIR')
cem('PAIR', 'pair_B', TOP, None)                 # B: both coils in the EM
cem('PAIR', 'pair_A', TOP, ["L1", "L2"])        # A: both coils cut, each one's own 2-port back on its pins
print('written', HERE)
