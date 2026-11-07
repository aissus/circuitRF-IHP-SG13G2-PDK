#!/bin/bash
# Compiles the kit's VBIC models with OpenVAF from VBIC 1.3's public Verilog-A source. They are not
# distributed with the kit (see NOTICE), so every kit build, and every user of a released kit, makes them:
#     generator/build-vbic.sh [kit folder]        (default: kit/IHP_SG13G2 beside generator/)
# - models/osdi/vbic_1p3_5t.osdi, which the HBT cells run. Needs only OpenVAF (openvaf on PATH, or OPENVAF=).
# - With the IHP PDK at $PDKPATH (as in IIC-OSIC-TOOLS) and python3, also harmonicaRF's devices:
#   vbic_1p3_bce.osdi and npn13G2{,l,v}.osdi, each HBT compiled whole with the PDK's scaling inside.
# The source is VACASK's copy at the commit below: IIC-OSIC-TOOLS has it, anywhere else it is fetched.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
K=${1:-$(dirname "$S")/kit/IHP_SG13G2}
OPENVAF=${OPENVAF:-openvaf}
VACASK_COMMIT=89e888d993aa9afbeedde5636c495d9a58ec3b2a
command -v "$OPENVAF" >/dev/null || { echo "OpenVAF not found: put openvaf on PATH or set OPENVAF" >&2; exit 1; }
mkdir -p "$K/models/osdi"

SRC=${VBIC_SRC:-/foss/tools/vacask/src/vacask/devices/vbic}
if [ ! -f "$SRC/vbic_1p3.va" ]; then
    SRC=$(mktemp -d); trap 'rm -rf "$SRC"' EXIT
    for f in vbic_1p3.va disciplines.vams constants.vams cmcGeneralMacrosAndDefines.va cmcStandardModelMacros.va; do
        curl -fsSL -o "$SRC/$f" "https://codeberg.org/arpadbuermen/VACASK/raw/commit/$VACASK_COMMIT/devices/vbic/$f"
    done
fi

# c, b, e, s and the thermal node dt: the terminals the cells wire. VACASK's own options for this file
# (devices/CMakeLists.txt): __NGSPICE__ selects ngspice's pnjlim junction limiting.
"$OPENVAF" -D__NGSPICE__ -DfiveTerminal --allow variant_const_simparam -I "$SRC" "$SRC/vbic_1p3.va" \
    -o "$K/models/osdi/vbic_1p3_5t.osdi"
echo "built $K/models/osdi/vbic_1p3_5t.osdi"

if [ -n "${PDKPATH:-}" ] && command -v python3 >/dev/null; then
    export VBIC_SRC=$SRC
    python3 "$S/harmonica_ihp.py" osdi "$K/models/osdi/vbic_1p3_bce.osdi"
    for d in npn13G2 npn13G2l npn13G2v; do
        python3 "$S/harmonica_ihp.py" nx-osdi $d "$K/models/osdi/$d.osdi"
    done
else
    echo "PDKPATH not set: harmonicaRF's devices skipped (the kit's cells do not need them)"
fi
