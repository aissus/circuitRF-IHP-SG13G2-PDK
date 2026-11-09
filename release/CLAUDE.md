# IHP SG13G2 kit for circuitRF

This folder is a released device kit for circuitRF on the IHP SG13G2 130 nm SiGe BiCMOS process, with an
example workspace. To design, simulate or run EM with it, use the skill in
`.claude/skills/ihp-sg13g2-kit/SKILL.md`. It covers the cells, workspaces, analyses, EM and the MCP tools.

## Contents

| Path | Contents |
|---|---|
| `kit/IHP_SG13G2/` | The kit: one folder per cell, `tech/IHP_SG13G2.ctech`, `models/osdi/`, `README.md`, `BUILD`, `VALIDATION`. It is generated, so do not edit it. |
| `examples/` | A circuitRF workspace on the kit (`examples/.cws`), with one bench per task. |
| `generator/` | The kit's generator. `build-vbic.sh` compiles the VBIC models. `circuitrf-ihp-workspace` starts a workspace. |
| `.mcp.json` | circuitRF's MCP server: `circuitrf serve --root .`. |
| `README.md`, `LICENSE`, `NOTICE` | The user guide and the license (Apache-2.0, like the IHP PDK). |

## Setup

1. **circuitRF 1.7.5 or newer.**
   - `.mcp.json` runs `circuitrf` from `PATH`. If `circuitrf --version` does not answer, set `"command"` to the
     executable's full path (macOS: `/Applications/circuitRF.app/Contents/MacOS/circuitRF`).
   - `circuitrf serve --root . --print-config` prints the right configuration.
   - The server root is this folder. The server reaches the kit, the examples and any workspace you create here,
     and nothing outside.
2. **The HBT model, once.** If `kit/IHP_SG13G2/models/osdi/vbic_1p3_5t.osdi` is missing, every HBT bench fails
   with `There is no build of 'vbic_1p3_5t.osdi'`. Run `generator/build-vbic.sh` from this folder:
   - It needs `openvaf` on `PATH`, or `OPENVAF=`.
   - With `PDKPATH` set to the IHP PDK, it also builds harmonicaRF's devices.
   - Resistors, the MIM capacitor and EM work without it.
3. **Check:** `circuitrf check examples --summary` must report 0 errors. Four warnings are expected: two
   schematics declare no analysis, and the technology has no DRC rules.

## Working here

- **The example workspace:** open `examples/.cws`. Its benches show each analysis on the kit.
  `examples/README.md` describes each bench and how it runs.
- **New designs:** make a new workspace in this folder, beside `kit/`. Either:
  - run `generator/circuitrf-ihp-workspace <dir>` (it writes absolute paths), or
  - write the relative `.cws` that the skill shows.

  Cells are placed as `ws://IHP_SG13G2/<cell>`.
- **Machine paths:** `examples/.cws` names the PDK at `/foss/pdks/ihp-sg13g2` (`PdkRefs`), as circuitRF's import
  recorded it, and so does the PCell declaration in `examples/ihp-sg13g2-pcells/`. They give the PDK's own parts and
  IHP's PCells where the PDK is installed there; with the PDK elsewhere, import it again:
  `circuitrf import pdk <PDK> --into examples`. The kit's cells do not need it.
- **EM solvers:**
  - `circuitrf solver list` shows what is installed.
  - EMerge installs with `circuitrf solver install emerge --yes`.
  - Palace and openEMS come from your own install, or from IIC-OSIC-TOOLS.
  - Check an EM setup's cost before running it: `circuitrf em <setup.cem> --dry-run`. On-chip runs take hours
    (Palace 1 h 18 min, planar MoM about 2 h for the example inductor on 16 cores).
- **Licensing:** the compiled VBIC models (`vbic_1p3*.osdi`, `npn13G2*.osdi`) are built on your machine from
  VBIC's source and are not part of this release. If you pass the kit on, leave them out (see NOTICE).
