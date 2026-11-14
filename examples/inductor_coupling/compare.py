#!/usr/bin/env python3
"""compare.py [display]: L, Q and coupling of the two coils in each run, from the Touchstone files in results/.

  B  results/pair_B.s5p        pair_B: both coils in the EM, with the plane and the feeds
  A  results/pair_A_cosim.s5p  pair_A: both coils cut, each coil's own 2-port back (the run of pair_A_cosim.cnl)
  S  results/pair_sch.s4p      the PAIR schematic: the two coils' own 2-ports and nothing else (k = 0 by construction)

Ports 1, 2 = L1's feeds (LA, LB), 3, 4 = L2's (LA, LB), 5 = the plane's tie. The tie is shorted, and so are ports
2 and 4: what is left is the 2-port (1, 3) that sees one end of each coil, the other end on the reference.
  L = Im(Z11)/w, Q = Im(Z11)/Re(Z11) (L2 from Z22),  k = Im(Z12)/sqrt(Im(Z11) Im(Z22)),
  |S31| from the 4-port with only the tie shorted, the other ports in 50 Ohm; that 4-port is written to
  results/pair_{B,A}_tie.s4p. `display` (inside the image) draws coupling.cdd and pictures/coupling.png from them.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'blackbox_common'))
import numpy as np
from blackbox import touchstone, y_of, s_of, keep, row, write_s, display

AT = [1, 4, 10, 16, 22, 28, 34, 40]
print('%-28s' % 'GHz' + ''.join('%9g' % g for g in AT))
for tag, path in (('B', 'results/pair_B.s5p'), ('A', 'results/pair_A_cosim.s5p'), ('S', 'results/pair_sch.s4p')):
    if not os.path.exists(path):
        print(f'{tag}: {path} not there yet')
        continue
    f, s, z0 = touchstone(path)
    y = y_of(s, z0)
    z = np.linalg.inv(keep(y, [1, 3]))
    w = 2e9 * np.pi * f
    s4 = s_of(keep(y, [1, 2, 3, 4]), z0)
    row(f'{tag}  L1 pH', f, z[:, 0, 0].imag / w * 1e12, '%.0f', AT)
    row(f'{tag}  Q1', f, z[:, 0, 0].imag / z[:, 0, 0].real, '%.1f', AT)
    row(f'{tag}  L2 pH', f, z[:, 1, 1].imag / w * 1e12, '%.0f', AT)
    row(f'{tag}  Q2', f, z[:, 1, 1].imag / z[:, 1, 1].real, '%.1f', AT)
    row(f'{tag}  k', f, z[:, 0, 1].imag / np.sqrt(z[:, 0, 0].imag * z[:, 1, 1].imag), '%.1e', AT)
    row(f'{tag}  |S31| dB (L1.LA to L2.LA)', f, 20 * np.log10(abs(s4[:, 2, 0]) + 1e-30), '%.1f', AT)
    if tag != 'S':
        write_s(f'results/pair_{tag}_tie.s4p', f, s4, z0, f'compare.py: {path} with port 5 (the tie) shorted')
if 'display' in sys.argv:
    display('coupling', [('B', 'results/pair_B_tie.s4p'), ('A', 'results/pair_A_tie.s4p')], [(3, 1), (4, 2), (2, 1)])
    print('wrote coupling.cdd, pictures/coupling.png')
