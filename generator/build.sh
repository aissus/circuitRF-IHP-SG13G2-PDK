#!/bin/bash
# Build the IHP SG13G2 kit for circuitRF from this folder and the image's PDK:
#     ./kit.sh generator/build.sh                 (from the repository's top folder)
# The kit lands in kit/IHP_SG13G2 (K= overrides it). Its cells name their models
# relative to themselves, so the built kit can be copied or moved anywhere. The
# old kit is set aside while the new one builds: if any step or check fails, the
# old kit is put back, so a mismatch never ships.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
K=${K:-$(dirname "$S")/kit/IHP_SG13G2}
M=$PDKPATH/libs.tech/ngspice/models
mkdir -p "${K%/*}"

# The old kit is set aside under a name of its own: a circuitRF still running keeps its .osdi files
# open, and NFS cannot delete those (they linger as .nfs* until it exits), so removing old
# copies is best-effort and must not stop the build.
P=$K.prev.$$
rm -rf "$K".prev* 2>/dev/null || true
[ -e "$K" ] && mv "$K" "$P"
trap 'echo "kit build FAILED; the previous kit is kept" >&2; rm -rf "$K"; [ -e "$P" ] && mv "$P" "$K"' ERR

mkdir -p "$K/models/osdi" "$K/models/ihp"
# The compact models the cells run: CMC R3 from the PDK, VBIC 1.3 from VACASK,
# both compiled by this image's OpenVAF.
cp "$PDKPATH/libs.tech/ngspice/osdi/r3_cmc.osdi" /foss/tools/vacask/lib/vacask/mod/vbic_1p3_5t.osdi "$K/models/osdi/"
for d in npn13G2 npn13G2l npn13G2v; do for n in 1 2 4 8; do
    python3 "$S/ihp2va.py" "$M/sg13g2_hbt_mod.lib" $d --nx $n \
        --cornerlib "$M/cornerHBT.lib" -o "$K/models/ihp/${d}_nx$n.va"
done; done
python3 "$S/ihp2crf.py" --pdk "$PDKPATH" --out "$K"
python3 "$S/qucs2csym.py" --kit "$K"
python3 "$S/harmonica_ihp.py" osdi "$K/models/osdi/vbic_1p3_bce.osdi"
# harmonicaRF's devices: VBIC compiled per HBT with the PDK's scaling inside, so the only
# parameters are Nx (le), corner and temp (the documents are in examples/harmonica)
for d in npn13G2 npn13G2l npn13G2v; do
    python3 "$S/harmonica_ihp.py" nx-osdi $d "$K/models/osdi/$d.osdi"
done
# against the PDK's own models in ngspice and Xyce, then as circuitRF reads it
python3 "$S/validate_ihp_kit.py" --kit "$K" | tee "$K/VALIDATION"
circuitrf check "$K" --summary

# The examples' own copy of the technology (a workspace owns its technology), and their harmonicaRF
# documents: a .charm names its compiled DUT by absolute path, so they are made for this kit, here.
E=$(dirname "$S")/examples
mkdir -p "$E/tech" "$E/harmonica"
cp "$K"/tech/*.ctech "$E/tech/"
for d in npn13G2 npn13G2v; do for n in 1 2 4 8; do
    python3 "$S/harmonica_ihp.py" charm "$E/harmonica/${d}_Nx${n}_50GHz.charm" --device $d --nx $n \
        --osdi "$K/models/osdi/$d.osdi"
done; done

{ echo "built $(date -Iseconds) by generator/build.sh"
  echo "PDK commit $(cat "$PDKPATH/COMMIT" 2>/dev/null || echo '?')"
  echo "circuitRF $(circuitrf --version)"
  echo "validation: $(tail -1 "$K/VALIDATION")"; } > "$K/BUILD"
trap - ERR
rm -rf "$P" 2>/dev/null || true
echo "kit built: $K"
