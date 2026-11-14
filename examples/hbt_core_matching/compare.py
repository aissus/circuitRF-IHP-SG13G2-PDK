#!/usr/bin/env python3
"""compare.py [display]: |S21|, |S11|, |S22| and stability of the core's benches, from results/:

  (i)   results/core_i_tb.s2p    core_i's co-simulation: Q1, C1, C2 cut; coils, lines and plane in the EM
  (ii)  results/core_ii_tb.s2p   core_ii's: Q1, C1, C2 and both coils cut, each coil's own 2-port back
  sch   results/core_sch_tb.s2p  the CORE schematic: the same models with ideal wires (no plane, no interconnect)

K = (1 - |S11|^2 - |S22|^2 + |D|^2) / (2 |S12 S21|),  mu = (1 - |S11|^2) / (|S22 - D S11*| + |S12 S21|),
D = S11 S22 - S12 S21: unconditionally stable when mu > 1. `display` (inside the image) draws core.cdd and
pictures/core.png.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'blackbox_common'))
import numpy as np
from blackbox import touchstone, row, display

AT = [4, 10, 16, 22, 28, 34, 40]           # core_i and core_ii's EM points
db = lambda x: 20 * np.log10(abs(x))
print('%-28s' % 'GHz' + ''.join('%9g' % g for g in AT))
for tag in ('i', 'ii', 'sch'):
    path = f'results/core_{tag}_tb.s2p'
    if not os.path.exists(path):
        print(f'({tag}): {path} not there yet')
        continue
    f, s, _ = touchstone(path)
    s11, s21, s12, s22 = s[:, 0, 0], s[:, 1, 0], s[:, 0, 1], s[:, 1, 1]
    D = s11 * s22 - s12 * s21
    row(f'({tag}) |S21| dB', f, db(s21), '%.2f', AT)
    row(f'({tag}) |S11| dB', f, db(s11), '%.2f', AT)
    row(f'({tag}) |S22| dB', f, db(s22), '%.2f', AT)
    row(f'({tag}) K', f, (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(D) ** 2) / (2 * abs(s12 * s21)), '%.2f', AT)
    row(f'({tag}) mu', f, (1 - abs(s11) ** 2) / (abs(s22 - D * np.conj(s11)) + abs(s12 * s21)), '%.2f', AT)
if 'display' in sys.argv:
    display('core', [('(i)', 'results/core_i_tb.s2p'), ('(ii)', 'results/core_ii_tb.s2p'),
                     ('sch', 'results/core_sch_tb.s2p')], [(2, 1), (1, 1), (2, 2)])
    print('wrote core.cdd, pictures/core.png')
