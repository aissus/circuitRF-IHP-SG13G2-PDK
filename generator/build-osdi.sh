#!/bin/bash
# Compiles the PDK's PSP 103 and R3 (CMC) models for each platform circuitRF runs on, from the PDK's own
# sources with its own options (libs.tech/verilog-a/openvaf-compile-va.sh), for a generic processor:
#     generator/build-osdi.sh [folder]            (default: osdi/ beside generator/)
# It writes <folder>/<platform>/{psp103,r3_cmc}.osdi, and <folder>/SOURCES, the checksums of the sources.
# build.sh checks SOURCES against the PDK, then copies the builds into the kit's models/osdi/. circuitRF
# loads models/osdi/<platform>/<name>.osdi first and models/osdi/<name>.osdi (the PDK's Linux x86-64 build)
# otherwise. RIDS= selects platforms (default: all six) and OPENVAF= names the compiler.
#
# OpenVAF links by running `ld` (link.exe for win-arm64). For each other operating system, this script
# puts a stand-in first on PATH that runs that platform's linker:
#   win-x64              x86_64-w64-mingw32-gcc (MinGW-w64)
#   linux-arm64          ld.lld
#   osx-x64, osx-arm64   ld64.lld; the C library resolves in the loading process, as in a Linux build
#   win-arm64            MSVC's link.exe, so it is built on Windows
# The arm64 platforms also need an OpenVAF built with LLVM's AArch64 target. The image's OpenVAF has
# only x86-64. A platform that does not build is reported and left as it was, and the exit status is 1.
set -euo pipefail
S=$(dirname "$(readlink -f "$0")")
O=${1:-$(dirname "$S")/osdi}
V=${PDK_VA:-$PDKPATH/libs.tech/verilog-a}
OPENVAF=${OPENVAF:-openvaf-r}
declare -A T=([linux-x64]=x86_64-unknown-linux [linux-arm64]=aarch64-unknown-linux
              [osx-x64]=x86_64-apple-darwin [osx-arm64]=aarch64-apple-darwin
              [win-x64]=x86_64-pc-windows-gnu [win-arm64]=aarch64-pc-windows)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
failed=()

for rid in ${RIDS:-linux-x64 linux-arm64 osx-x64 osx-arm64 win-x64 win-arm64}; do
    mkdir -p "$W/$rid/bin"
    case $rid in
        win-x64)     printf '#!/bin/sh\nexec x86_64-w64-mingw32-gcc -Wl,--no-insert-timestamp,--disable-auto-image-base "$@"\n' ;;
        linux-arm64) printf '#!/bin/sh\nexec ld.lld "$@"\n' ;;
        osx-*)       a=${T[$rid]%%-*}; [ "$a" = aarch64 ] && a="arm64 -platform_version macos 11.0 11.0" \
                         || a="x86_64 -platform_version macos 10.15 10.15"
                     # OpenVAF passes clang's options; ld64.lld takes its own, and there is no SDK for -lSystem.
                     printf '#!/bin/bash\na=()\nfor x; do case $x in -Wl,*|-dynamiclib|-lSystem) ;; *) a+=("$x") ;; esac; done\n'
                     printf 'exec ld64.lld -dylib -undefined dynamic_lookup -arch %s "${a[@]}"\n' "$a" ;;
    esac > "$W/$rid/bin/ld"
    chmod +x "$W/$rid/bin/ld"; [ -s "$W/$rid/bin/ld" ] || rm "$W/$rid/bin/ld"
    for m in r3_cmc psp103; do
        # OpenVAF can exit 0 on a failed link, so the output file is the test.
        PATH=$W/$rid/bin:$PATH "$OPENVAF" -D__NGSPICE__ --target_cpu generic --target "${T[$rid]}" \
            -o "$W/$rid/$m.osdi" "$V/$m/$m.va" > "$W/$rid/log" 2>&1 || true
        [ -s "$W/$rid/$m.osdi" ] || break
    done
    if [ -s "$W/$rid/psp103.osdi" ] && [ -s "$W/$rid/r3_cmc.osdi" ]; then
        mkdir -p "$O/$rid" && cp "$W/$rid"/{psp103,r3_cmc}.osdi "$O/$rid/"
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

(cd "$V" && sha256sum psp103/*.va psp103/*.include r3_cmc/r3_cmc.va r3_cmc/*.include) > "$O/SOURCES"
[ ${#failed[@]} -eq 0 ] || { echo "not built: ${failed[*]}" >&2; exit 1; }
