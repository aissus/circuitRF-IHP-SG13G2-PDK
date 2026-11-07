#!/bin/bash
# kit.sh <cmd...>   run a command in kit.sif (built from kit.def), from this folder, e.g.
#   ./kit.sh generator/build.sh
# HOME is .home/ here, so a run writes nothing outside this folder.
D=$(dirname "$(readlink -f "$0")")
mkdir -p "$D/.home"
args=(--cleanenv --bind "$D" --pwd "$D" --home "$D/.home")
# Display, for opening the examples in circuitRF. Some remote desktops keep XAUTHORITY outside the home directory.
[ -z "$XAUTHORITY" ] && [ -f "$HOME/.Xauthority" ] && XAUTHORITY=$HOME/.Xauthority
[ -n "$DISPLAY" ] && args+=(--env "DISPLAY=$DISPLAY")
[ -f "$XAUTHORITY" ] && args+=(--bind "$XAUTHORITY" --env "XAUTHORITY=$XAUTHORITY")
# How many Palace ranks and solver threads a run may take (kit.def's Palace wrapper reads PALACE_NP).
for v in PALACE_NP OMP_NUM_THREADS; do [ -n "${!v}" ] && args+=(--env "$v=${!v}"); done
# The base sets PATH, PDKPATH and the tools' variables in its profile, which --cleanenv skips. Its
# [INFO] lines go to stderr so they never mix with a tool's output.
exec apptainer exec "${args[@]}" "$D/kit.sif" bash -c '
    source /etc/profile.d/iic-osic-tools-setup.sh >&2
    exec "$@"' kit "$@"
