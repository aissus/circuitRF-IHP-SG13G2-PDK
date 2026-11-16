#!/bin/bash
# Compiles the kit's VBIC models with OpenVAF for this machine, from VBIC 1.3's Verilog-A source in
# generator/vbic/ (VA-Models' copy, see NOTICE):
#     generator/build-vbic.sh [kit folder]        (default: kit/IHP_SG13G2 beside generator/)
# - models/osdi/vbic_1p3_5t.osdi, which the HBT cells run on a platform with no build in
#   models/osdi/<platform>/ (build-osdi.sh makes those), and the PDK's own HBTs on every platform (the
#   stand-in circuitrf-ihp-workspace declares names this file). Needs only OpenVAF (openvaf on PATH, or
#   OPENVAF=).
# - With the IHP PDK at $PDKPATH (as in IIC-OSIC-TOOLS) and python3, also harmonicaRF's devices:
#   vbic_1p3_bce.osdi and npn13G2{,l,v}.osdi, each HBT compiled whole with the PDK's scaling inside.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
K=${1:-$(dirname "$S")/kit/IHP_SG13G2}
OPENVAF=${OPENVAF:-openvaf}
command -v "$OPENVAF" >/dev/null || { echo "OpenVAF not found: put openvaf on PATH or set OPENVAF" >&2; exit 1; }
mkdir -p "$K/models/osdi"

# c, b, e, s and the thermal node dt: the terminals the cells wire. VACASK's own options for this file
# (devices/CMakeLists.txt): __NGSPICE__ selects ngspice's pnjlim junction limiting.
"$OPENVAF" -D__NGSPICE__ -DfiveTerminal --allow variant_const_simparam -I "$S/vbic" "$S/vbic/vbic_1p3.va" \
    -o "$K/models/osdi/vbic_1p3_5t.osdi"
echo "built $K/models/osdi/vbic_1p3_5t.osdi"

if [ -n "${PDKPATH:-}" ] && command -v python3 >/dev/null; then
    python3 "$S/harmonica_ihp.py" osdi "$K/models/osdi/vbic_1p3_bce.osdi"
    for d in npn13G2 npn13G2l npn13G2v; do
        python3 "$S/harmonica_ihp.py" nx-osdi $d "$K/models/osdi/$d.osdi"
    done
else
    echo "PDKPATH not set: harmonicaRF's devices skipped (the kit's cells do not need them)"
fi
