#!/bin/bash
# Build the kit and pack it as a release archive, inside the base image (kit.def's From:):
#     ./kit.sh ci/build-release.sh                                   (here, in kit.sif)
#     docker run ... <the base> --skip ci/build-release.sh           (.github/workflows/release.yml)
# Writes dist/circuitRF-IHP-SG13G2-<version>.zip, the kit with its example workspace ready to unpack and
# use (release/README.md says how), and its .sha256. <version> is the tag on HEAD, else git describe;
# KIT_VERSION overrides it.

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

# The release is Apache-2.0 throughout, as the PDK: the VBIC-derived models stay out, and
# generator/build-vbic.sh compiles them where the kit is used (see NOTICE). The example workspace comes
# with its technology copy; its harmonicaRF documents name this machine's paths, so they stay out too.
n=circuitRF-IHP-SG13G2-$v
R=dist/$n
rm -rf dist && mkdir -p "$R/kit" "$R/examples/tech"
cp -r kit/IHP_SG13G2 "$R/kit/"
rm -f "$R"/kit/IHP_SG13G2/models/osdi/{vbic_1p3_5t,vbic_1p3_bce,npn13G2,npn13G2l,npn13G2v}.osdi
git ls-files -z generator examples .claude | xargs -0 cp --parents -t "$R"
cp examples/tech/*.ctech "$R/examples/tech/"
cp LICENSE NOTICE "$R/"
cp release/README.md release/CLAUDE.md release/.mcp.json "$R/"
if ls "$R"/kit/IHP_SG13G2/models/osdi | grep -q -E 'vbic|npn13G2'; then
    echo "a VBIC-derived model is in the release" >&2; exit 1
fi
(cd dist && zip -qrX "$n.zip" "$n" && rm -rf "$n" && sha256sum "$n.zip" > "$n.zip.sha256")
ls -l dist
cat kit/IHP_SG13G2/BUILD
