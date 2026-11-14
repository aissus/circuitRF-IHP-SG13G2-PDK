#!/usr/bin/env python3
"""tb.py <in.cnl> <out.cnl> [--core] [--grid 4,40,7]: a bench round a netlist circuitRF wrote (a run's _cosim.cnl, or
a schematic's `circuitrf netlist`), with an S-parameter analysis on the EM runs' own points (default 1-40 GHz, 14).

--core (step 2): P1 and P2 get a 1 uF DC block; P3, the plane's tie, is shorted to the reference; and Q1's pins are
held at the bias through 1 mH each (VBE on B, VCC on C, 0 on E), because an EM block has no 0 Hz point to bias
through. 1 mH is an open from 1 GHz up. ICC and IB read the collector and base currents.
The bench is written beside the netlist's results/ folder or in tb/: File="results/ is rewritten to match. circuitRF
names the kit's compiled models by absolute path; the bench names them relative to itself, so it holds no machine path.
"""
import os, re, sys

CORE = '--core' in sys.argv
F0, F1, N = (sys.argv[sys.argv.index('--grid') + 1].split(',') if '--grid' in sys.argv else ('1', '40', '14'))
src, dst = [a for a in sys.argv[1:] if a not in ('--core', '--grid', f'{F0},{F1},{N}')]
here = os.path.dirname(os.path.abspath(dst))
rel = os.path.relpath('results', here)
out = ['VBE = 0.88', 'VCC = 1.5'] if CORE else []
for line in open(src).read().splitlines():
    if line.startswith(('analysis ', 'labelednets')):
        continue
    line = line.replace('File="results/', f'File="{rel}/')
    line = re.sub(r'File="(/[^"]+)"', lambda m: f'File="{os.path.relpath(m[1], here)}"', line)
    m = re.match(r'^Port:P(\d+)\s+(\S+)\s+0\b', line)
    if CORE and m:
        k, n = m.groups()
        out += ([f'Port:P{k} x{k} 0 Num={k} Z=50 Ohm', f'C:CB{k} x{k} {n} C=1uF'] if k in '12' else
                [f'Vdc:VTIE {n} 0 Vdc=0'])
        continue
    out.append(line)
    q = re.match(r'^npn13G2:Q1\s+(\S+)\s+(\S+)\s+(\S+)', line)
    if CORE and q:
        for node, v, probe in zip(q.groups(), ('VCC', 'VBE', '0'), ('ICC', 'IB', None)):
            if node == '0':
                continue
            out.append(f'L:LF_{node} {node} f_{node} L=1mH')
            out += ([f'Vdc:VF_{node} s_{node} 0 Vdc={v}', f'IProbe:{probe} s_{node} f_{node}'] if probe else
                    [f'Vdc:VF_{node} f_{node} 0 Vdc={v}'])
if CORE:
    out.append('analysis DC1 type=dc')
out.append(f'analysis SP1 type=sparam start="{F0}" startUnit=GHz stop="{F1}" stopUnit=GHz npts={N}')
open(dst, 'w').write('\n'.join(out) + '\n')
