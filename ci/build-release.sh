#!/bin/bash
# Build the kit and pack it as a release archive, inside the base image (kit.def's From:):
#     ./kit.sh ci/build-release.sh                                   (here, in kit.sif)
#     docker run ... <the base> --skip ci/build-release.sh           (.github/workflows/release.yml)
# Writes dist/circuitRF-IHP-SG13G2-kit-<version>.tar.gz (IHP_SG13G2/, LICENSE, NOTICE) and its
# .sha256. <version> is the tag on HEAD, else git describe; KIT_VERSION overrides it.

# The base sets PATH, PDKPATH and the tools' variables in its profile. The profile reads unset
# variables, so it runs before set -u.
[ -n "${PDKPATH:-}" ] || source /etc/profile.d/iic-osic-tools-setup.sh >&2
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

# Named first, so a checkout git refuses fails before the build, not after it.
v=${KIT_VERSION:-$(git describe --tags --exact-match 2>/dev/null || git describe --always --dirty)}

# The base has no circuitRF: fetch the release kit.def installs, so kit.def stays the one place
# its version is named.
if ! command -v circuitrf >/dev/null; then
    url=$(grep -o 'https://[^ ]*/circuitRF-[^ ]*-linux-x64\.tar\.gz' kit.def)
    c=${url##*/circuitRF-}; c=${c%-linux-x64.tar.gz}
    mkdir -p "$HOME/bin"
    curl -fsSL "$url" | tar -xz -C "$HOME"
    ln -sf "$HOME/circuitRF-$c/app-$c/circuitRF" "$HOME/bin/circuitrf"
    export PATH=$HOME/bin:$PATH
fi

# The kit is generated from, and validated against, the PDK commit kit.def checks.
want=$(sed -n 's/.*COMMIT)" = \([0-9a-f]*\)$/\1/p' kit.def)
have=$(cat "$PDKPATH/COMMIT")
[ -n "$want" ] && [ "$have" = "$want" ] || { echo "PDK commit $have, kit.def wants $want" >&2; exit 1; }

generator/build.sh

n=circuitRF-IHP-SG13G2-kit-$v
rm -rf dist && mkdir dist
tar -czf "dist/$n.tar.gz" --owner=0 --group=0 -C kit IHP_SG13G2 -C "$PWD" LICENSE NOTICE
(cd dist && sha256sum "$n.tar.gz" > "$n.tar.gz.sha256")
ls -l dist
cat kit/IHP_SG13G2/BUILD
