#!/bin/bash
# Regenerates the pictures circuitRF exports for the documentation, in two versions:
#   docs/images/<name>.png        as circuitRF exports them (data displays with a transparent background)
#   docs/images/white/<name>.png  on white, for pages and dark themes
#     ./kit.sh docs/make-figures.sh            (from the repository's top folder, after generator/build.sh)
# It runs the circuit benches first. The inductor's EM setups take hours and are not run here: run them
# (see examples/README.md) before this, or inductor_TB is skipped. The pictures from circuitRF's window
# (docs/images/gui/) are screenshots, not exports; examples/README.md says how they were taken.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
I=docs/images W=docs/images/white
mkdir -p "$I" "$W"

( cd examples
  circuitrf hb HBT_IcVce/schematic/HBT_IcVce.csch -a SW2 -o results/HBT_IcVce.npy
  circuitrf hb Resistors/schematic/Resistors.csch -a SW1 -o results/Resistors.npy
  circuitrf sparam MIM_Cap/schematic/MIM_Cap.csch -o results/MIM_Cap.npy
  circuitrf hb HBT_Ic/schematic/HBT_Ic.csch -a SW0 -o results/HBT_Ic.npy
  circuitrf hb HBT_fT_fmax/schematic/HBT_fT_fmax.csch -a SW0 -o results/HBT_fT_fmax.npy
  circuitrf lp HBT_Loadpull/schematic/HBT_Loadpull.csch -o results/HBT_Loadpull.npy
  if ls results/inductor.palace.s2p results/inductor.emerge.s2p results/inductor_mom.s1p >/dev/null 2>&1; then
      circuitrf sparam inductor_TB/schematic/inductor_TB.csch -o results/inductor_TB.npy
  else echo "inductor_TB: the EM results are missing; its display is left as it is" >&2; fi ) > /dev/null

# Data displays: their own palette; white = an opaque background.
for d in HBT_IcVce Resistors MIM_Cap HBT_fT_fmax HBT_Loadpull inductor_TB; do
    [ -f examples/results/$d.npy ] || continue
    circuitrf render examples/results/$d.cdd -o $I/$d.png --scale 2
    circuitrf render examples/results/$d.cdd -o $W/$d.png --scale 2 --background opaque
done
# Layouts and schematics: the theme's canvas; white = docs/white.ccolor.
for f in examples/inductor/layout/inductor.clay examples/inductor/layout/inductor_mom.clay \
         examples/Kit_cells/schematic/Kit_cells.csch; do
    n=$(basename "${f%.*}")
    circuitrf render "$f" -o $I/$n.png --fit
    circuitrf render "$f" -o $W/$n.png --fit --theme docs/white.ccolor
done
