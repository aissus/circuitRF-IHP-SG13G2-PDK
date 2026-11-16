#!/bin/bash
# Compiles the kit's compact models for each platform circuitRF runs on, for a generic processor: the PDK's
# PSP 103 and R3 (CMC) from its own sources with its own options (libs.tech/verilog-a/openvaf-compile-va.sh),
# VBIC 1.3 from generator/vbic/ with build-vbic.sh's options, and harmonicaRF's devices (harmonica_ihp.py, from
# the PDK's HBT library):
#     generator/build-osdi.sh [folder]            (default: osdi/ beside generator/)
# It writes <folder>/<platform>/{psp103,r3_cmc,vbic_1p3_5t,vbic_1p3_bce,npn13G2,npn13G2l,npn13G2v}.osdi, and
# <folder>/SOURCES, the checksums of the PDK's sources. build.sh checks SOURCES against the PDK, then copies
# the builds into the kit's models/osdi/. circuitRF loads models/osdi/<platform>/<name>.osdi first and
# models/osdi/<name>.osdi (a Linux x86-64 build: the PDK's, or build-vbic.sh's) otherwise. Needs the PDK at
# $PDKPATH and python3 (PYTHON= names another); RIDS= selects platforms (default: all six) and OPENVAF= names
# the compiler.
#
# OpenVAF links by running `ld` (MSVC's link.exe on Windows). For each other operating system, this script
# puts a stand-in first on PATH that runs that platform's linker:
#   linux-arm64          ld.lld
#   osx-x64, osx-arm64   ld64.lld; the C library resolves in the loading process, as in a Linux build
#   win-x64, win-arm64   MSVC's link.exe, so they are built on Windows. MinGW-w64 could link win-x64 here, but
#                        it puts GCC's runtime library (GPL-3.0, with its exception) into the DLL, and the kit
#                        ships no GPL-3.0 material.
# The arm64 platforms also need an OpenVAF built with LLVM's AArch64 target. The image's OpenVAF, like
# OpenVAF's published builds, has only x86-64. A platform counts as built when all seven models build; one that
# does not is reported and left as it was, and the exit status is 1.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
O=${1:-$(dirname "$S")/osdi}
V=$PDKPATH/libs.tech/verilog-a
OPENVAF=${OPENVAF:-openvaf-r}
PYTHON=${PYTHON:-python3}
models=(r3_cmc psp103 vbic_1p3_5t vbic_1p3_bce npn13G2 npn13G2l npn13G2v)
declare -A T=([linux-x64]=x86_64-unknown-linux [linux-arm64]=aarch64-unknown-linux
              [osx-x64]=x86_64-apple-darwin [osx-arm64]=aarch64-apple-darwin
              [win-x64]=x86_64-pc-windows [win-arm64]=aarch64-pc-windows)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
failed=()

for rid in ${RIDS:-linux-x64 linux-arm64 osx-x64 osx-arm64 win-x64 win-arm64}; do
    mkdir -p "$W/$rid/bin"
    case $rid in
        linux-arm64) printf '#!/bin/sh\nexec ld.lld "$@"\n' ;;
        osx-*)       a=${T[$rid]%%-*}; [ "$a" = aarch64 ] && a="arm64 -platform_version macos 11.0 11.0" \
                         || a="x86_64 -platform_version macos 10.15 10.15"
                     # OpenVAF passes clang's options; ld64.lld takes its own, and there is no SDK for -lSystem.
                     printf '#!/bin/bash\na=()\nfor x; do case $x in -Wl,*|-dynamiclib|-lSystem) ;; *) a+=("$x") ;; esac; done\n'
                     printf 'exec ld64.lld -dylib -undefined dynamic_lookup -arch %s "${a[@]}"\n' "$a" ;;
    esac > "$W/$rid/bin/ld"
    chmod +x "$W/$rid/bin/ld"; [ -s "$W/$rid/bin/ld" ] || rm "$W/$rid/bin/ld"
    f=(--target_cpu generic --target "${T[$rid]}")
    for m in "${models[@]}"; do
        # OpenVAF can exit 0 on a failed link, so the output file is the test.
        case $m in
            r3_cmc|psp103) PATH=$W/$rid/bin:$PATH "$OPENVAF" -D__NGSPICE__ "${f[@]}" -o "$W/$rid/$m.osdi" "$V/$m/$m.va" ;;
            vbic_1p3_5t)   PATH=$W/$rid/bin:$PATH "$OPENVAF" -D__NGSPICE__ "${f[@]}" -o "$W/$rid/$m.osdi" \
                               -DfiveTerminal --allow variant_const_simparam -I "$S/vbic" "$S/vbic/vbic_1p3.va" ;;
            # with build-vbic.sh's options, which are harmonica_ihp.py's own
            vbic_1p3_bce)  PATH=$W/$rid/bin:$PATH OPENVAF_FLAGS="${f[*]}" "$PYTHON" "$S/harmonica_ihp.py" osdi "$W/$rid/$m.osdi" ;;
            *)             PATH=$W/$rid/bin:$PATH OPENVAF_FLAGS="${f[*]}" "$PYTHON" "$S/harmonica_ihp.py" nx-osdi $m "$W/$rid/$m.osdi" ;;
        esac > "$W/$rid/log" 2>&1 || true
        [ -s "$W/$rid/$m.osdi" ] || break
    done
    # The loop stops at the first model that fails, so the last one built means all did.
    if [ -s "$W/$rid/${models[-1]}.osdi" ]; then
        mkdir -p "$O/$rid" && for m in "${models[@]}"; do cp "$W/$rid/$m.osdi" "$O/$rid/"; done
        echo "built $rid (${T[$rid]})"
    else
        # The first error, or for a crash the panic in the log OpenVAF names
        c=$(grep -a -o -m1 '[^"]*openvaf-crash-[0-9]*\.log' "$W/$rid/log" | head -1 || true)
        failed+=("$rid")
        echo "not built: $rid (${T[$rid]}): $(grep -a -h -m1 -E 'error|not found|No available targets' \
            "$W/$rid/log" ${c:+"$c"} | head -1 | sed 's/\x1b\[[0-9;]*m//g')" >&2
        rm -f ${c:+"$c"}
    fi
done

(cd "$V" && sha256sum psp103/*.va psp103/*.include r3_cmc/r3_cmc.va r3_cmc/*.include \
    ../ngspice/models/{sg13g2_hbt_mod,cornerHBT}.lib) > "$O/SOURCES"
[ ${#failed[@]} -eq 0 ] || { echo "not built: ${failed[*]}" >&2; exit 1; }
