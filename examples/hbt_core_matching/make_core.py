#!/usr/bin/env python3
"""Writes this example's cells, layouts and EM setups (coordinates in um). Inside the image, in this folder:

    python3 make_core.py

  IND_BIG, IND_SMALL  the two coil cells of inductor_coupling, written by the same shared code: same PCells, same
             own EM runs (ind_big, ind_small), same 2-port models.
  CORE       a single-finger npn13G2 (Q1, Nx = 1), common emitter, with those coils as its matching, in the same
             TopMetal1 ground plane at the same 75 um spacing:
             P1 - C1 (8 x 8 um cmim, shunt to the plane) - L1 (big coil, series) - Q1.B;  Q1.E - plane;
             Q1.C - L2 (small coil, series) - C2 (20 x 20 um cmim, DC block) - P2.  Drawn ports 1 (in), 2 (out),
             3 (the plane's tie). Setups: core_i (Q1, C1, C2 cut) and core_ii (Q1, C1, C2, L1, L2 cut).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'blackbox_common'))
from blackbox import *          # noqa: F401,F403

ws(HERE)
coil_cells()
# Everything below y = 0 sits in the plane's channel. Q1 at (XQ, YQ); its pins: B bottom bar (Metal1, face y YQ-1.26),
# C top bar (Metal1, face y YQ+1.25), E (Metal2, right face x XQ+0.925).
XQ, YQ = 84.0, -35.0
A1, A2 = 8.0, 20.0                          # C1 (shunt) and C2 (DC block): A x A um cmims
XC1, YC1 = -7.45 - 15 - A1, -40 - A1 / 2    # C1's origin (its MIM plate is [0, A1] x [0, A1])
XC2, YC2 = 165.0, -45.0
FREQ2 = dict(FREQ, StartExpr="4", NumPoints=7)                       # 4, 10, ... 40 GHz: on the coils' grid
LEVELS = [n for n in ALL if n != 'MIM']     # the cmims are cut, so nothing is left on MIM


def stack(x, y, lo, half=1.25):
    """A via stack from metal 'lo' up to TopMetal1 at (x, y): pads on each level between, 1 um vias."""
    mets, vias = [M1, M2, M3, M4, M5], [V1, V2, V3, V4, TV1]
    i = mets.index(lo)
    return ([rect(m, x - half, y - half, x + half, y + half) for m in mets[i:]] +
            [rect(v, x - 0.5, y - 0.5, x + 0.5, y + 0.5) for v in vias[i:]])


ccell('CORE')
xa, wa = lead(BIG, 0, -1)
xb, wb = lead(BIG, 0, 1)
x2a, w2a = lead(SMALL, XS, -1)
x2b, w2b = lead(SMALL, XS, 1)
sh = [PLANE,
      # P1 feed: L1.LA straight down to port 1; C1 hangs off it to the left
      rect(TM1, xa - wa / 2, -1, xa + wa / 2, -60), port('1', xa, -60, 'R90', TM1, 'P1'),
      rect(TM1, XC1 + A1 - 0.6, -42, xa - wa / 2, -38),                     # stub into C1's top plate (PLUS)
      rect(M5, -82, -42, XC1 - 0.6, -38), rect(TV1, -81.5, -41.5, -78.5, -38.5),  # C1.MINUS -> plane
      # L1.LB down and along to Q1's base stack; Metal1 up into B
      rect(TM1, xb - wb / 2, -1, xb + wb / 2, -52.7), rect(TM1, xb - wb / 2, -52.7, XQ + 2.7, -47.3),
      *stack(XQ, -50, M1), rect(M1, XQ - 0.75, -51.25, XQ + 0.75, YQ - 1.26),
      # Q1.C up a Metal1 strap to its stack, then TopMetal1 along and up into L2.LA
      rect(M1, XQ - 0.75, YQ + 1.25, XQ + 0.75, -25.0), *stack(XQ, -26.25, M1),
      rect(TM1, XQ - 2, -28.25, x2a + w2a / 2, -24.25), rect(TM1, x2a - w2a / 2, -28.25, x2a + w2a / 2, -1),
      # Q1.E on Metal2 to the right, up a stack onto a TopMetal1 finger of the plane
      rect(M2, XQ + 0.925, YQ - 0.75, XQ + 12.25, YQ + 0.75), *stack(XQ + 11, YQ, M2),
      rect(TM1, XQ + 8, YQ + 3, XQ + 18, YC - 5),
      # L2.LB down and right into C2's top plate (PLUS); C2.MINUS (Metal5) out to the right, up to the P2 feed
      rect(TM1, x2b - w2b / 2, -1, x2b + w2b / 2, -37), rect(TM1, x2b - w2b / 2, -37, XC2 + 0.6, -33),
      rect(M5, XC2 + A2 + 0.6, -37, 195, -33), rect(TV1, 192, -36.5, 195, -33.5),
      rect(TM1, 192, -37, 205, -33), port('2', 205, -35, 'R180', TM1, 'P2'),
      port('3', TIE_X, TIE_Y, 'R0', TM1)]
clay('CORE', sh, [inst(BIG, 0, 0, 'L1'), inst(SMALL, XS, 0, 'L2'), inst(NPN, XQ, YQ, 'Q1'),
                  inst(CAP[int(A1)], XC1, YC1, 'C1'), inst(CAP[int(A2)], XC2, YC2, 'C2')])
s = Sheet('CORE')
term(s, 'P1', 1, -2400, 500, 'in')
kit_part(s, 'C1', 'cap_cmim', -1800, 500, {'w': f'{A1:g}e-06', 'l': f'{A1:g}e-06'}, {'PLUS': 'in', 'MINUS': '0'})
coil(s, 'L1', 'IND_BIG', -1000, 0, 'in', 'b')
kit_part(s, 'Q1', 'npn13G2', 0, 0, {'Nx': 1}, {'c': 'c', 'b': 'b', 'e': '0', 'bn': '0'})
coil(s, 'L2', 'IND_SMALL', 1000, -600, 'c', 'o1')
kit_part(s, 'C2', 'cap_cmim', 1800, -600, {'w': f'{A2:g}e-06', 'l': f'{A2:g}e-06'}, {'PLUS': 'o1', 'MINUS': 'out'})
term(s, 'P2', 2, 2600, 0, 'out')
write_sheet(s, 'CORE')
# The two cmims are cut in both setups and get the kit's cap_cmim back: kept as copper, their Vmim arrays mesh to
# about 51,000 unknowns (88 GB per frequency point, past this machine's 52 GB); cut, about 22,000.
cem('CORE', 'core_i', LEVELS, ["Q1", "C1", "C2"], freq=FREQ2)                # (i): coils and lines in the EM
cem('CORE', 'core_ii', LEVELS, ["Q1", "C1", "C2", "L1", "L2"], freq=FREQ2)   # (ii): the coils cut too, own 2-ports back
print('written', HERE)
