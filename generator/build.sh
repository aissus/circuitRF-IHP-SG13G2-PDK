#!/bin/bash
# Build the IHP SG13G2 kit for circuitRF from this folder and the mounted PDK:
#     ./run.sh bash circuitrf-kit/build.sh        (from the host; setup.sh does it
#                                                 after every image rebuild)
# The kit lands in kits/IHP_SG13G2, which run.sh mounts at
# /foss/tools/circuitrf/kits, so workspaces and the cells' .osdi paths name it
# there. It is built in place (the cells hold absolute paths) with the old kit
# set aside: if any step or check fails, the old kit is put back, so a mismatch
# never ships.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
K=/foss/tools/circuitrf/kits/IHP_SG13G2
M=$PDKPATH/libs.tech/ngspice/models
[ -w "${K%/*}" ] || { echo "kits/ is not mounted: mkdir kits, then ./run.sh bash $0" >&2; exit 1; }

# The old kit is set aside under a name of its own: a circuitRF still running keeps its .osdi files
# open, and NFS cannot delete those (they linger as .nfs* until it exits), so removing old
# copies is best-effort and must not stop the build.
P=$K.prev.$$
rm -rf "$K".prev* 2>/dev/null || true
[ -e "$K" ] && mv "$K" "$P"
trap 'echo "kit build FAILED; the previous kit is kept" >&2; rm -rf "$K"; [ -e "$P" ] && mv "$P" "$K"' ERR

mkdir -p "$K/models/osdi" "$K/models/ihp" "$K/tools"
cp "$S"/*.py "$S/circuitrf-ihp-workspace" "$S/build.sh" "$K/tools/"
# The compact models the cells run: CMC R3 from the PDK, VBIC 1.3 from VACASK,
# both compiled by this image's OpenVAF.
cp "$PDKPATH/libs.tech/ngspice/osdi/r3_cmc.osdi" /foss/tools/vacask/lib/vacask/mod/vbic_1p3_5t.osdi "$K/models/osdi/"
for d in npn13G2 npn13G2l npn13G2v; do for n in 1 2 4 8; do
    python3 "$S/ihp2va.py" "$M/sg13g2_hbt_mod.lib" $d --nx $n \
        --cornerlib "$M/cornerHBT.lib" -o "$K/models/ihp/${d}_nx$n.va"
done; done
python3 "$S/ihp2crf.py" --pdk "$PDKPATH" --osdi "$K/models/osdi" --out "$K"
python3 "$S/qucs2csym.py" --kit "$K"
python3 "$S/harmonica_ihp.py" osdi "$K/models/osdi/vbic_1p3_bce.osdi"
# harmonicaRF's devices: VBIC compiled per HBT with the PDK's scaling inside, so the only
# parameters are Nx (le), corner and temp (the documents are in designs/IHP_kit_examples/harmonica)
for d in npn13G2 npn13G2l npn13G2v; do
    python3 "$S/harmonica_ihp.py" nx-osdi $d "$K/models/osdi/$d.osdi"
done
# against the PDK's own models in ngspice and Xyce, then as circuitRF reads it
python3 "$S/validate_ihp_kit.py" --kit "$K" | tee "$K/VALIDATION"
circuitrf cli check "$K" --summary

{ echo "built $(date -Iseconds) by circuitrf-kit/build.sh"
  echo "PDK commit $(cat "$PDKPATH/COMMIT" 2>/dev/null || echo '?')"
  echo "circuitRF $(circuitrf cli --version)"
  echo "validation: $(tail -1 "$K/VALIDATION")"; } > "$K/BUILD"
trap - ERR
rm -rf "$P" 2>/dev/null || true
echo "kit built: $K"
