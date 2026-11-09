# circuitRF-IHP-SG13G2-PDK

The IHP SG13G2 device kit for [circuitRF](https://github.com/potatobeanradio/circuitRF): the generator that
builds it from the IHP Open PDK, its validation against ngspice and Xyce, and an example workspace.
To design or simulate with the kit, use the skill in `.claude/skills/ihp-sg13g2-kit/SKILL.md`.

## Layout

| Path | Contents |
|---|---|
| `generator/` | `build.sh` runs the whole build: `ihp2va.py`, `ihp2crf.py` (cells, technology, the kit's `.cws`), `qucs2csym.py` (symbols), `build-vbic.sh` (VBIC 1.3 to OSDI, and harmonicaRF's devices through `harmonica_ihp.py`), `validate_ihp_kit.py`. `circuitrf-ihp-workspace` starts a workspace on the kit. |
| `kit/IHP_SG13G2/` | Build output, git-ignored: the cells, `tech/IHP_SG13G2.ctech`, `models/`, `VALIDATION`, `BUILD`. Never edit it; change the generator and rebuild. |
| `examples/` | One circuitRF workspace on the kit (`examples/.cws` references `../kit/IHP_SG13G2`) and on the IHP PDK as circuitRF imports it (`PdkRefs`, and the PCell declaration in `ihp-sg13g2-pcells/`, both written by `circuitrf import pdk`). `tech/`, `harmonica/` and `results/*` (except `*.cdd`) are written by the build and the runs. |
| `generator/` (PCells, overview) | `check_ihp_pcells.py` (each of the PDK's PCells, drawn by circuitRF from its import, against KLayout), `qucs2csch.py` (the Qucs-S gallery as `examples/Kit_cells`), `qucs_cells.json` (what works, with notes). |
| `docs/` | `make-figures.sh`, `white.ccolor`, `images/` (the pages use `images/white/`). |
| `ci/build-release.sh`, `.github/workflows/release.yml` | The release zip, built and validated in the base image. |
| `release/` | The `README.md`, `CLAUDE.md` and `.mcp.json` placed at the top of the release zip. |
| `kit.def`, `kit.sh` | The image (`hpretl/iic-osic-tools` plus circuitRF 1.7.5) and its launcher. |

## Running tools

Run everything in the image, through `./kit.sh <command...>` from the top folder. The image has ngspice, Xyce,
OpenVAF, the IHP PDK (`$PDKPATH`) and circuitRF 1.7.5.

- Build the image once: `apptainer build --fakeroot kit.sif kit.def`.
- `kit.sh` always starts in the top folder and uses `.home/` as HOME. Both `.home/` and `kit.sif` are git-ignored,
  so put scratch files under `.home/`. To run from another folder, use `./kit.sh bash -c 'cd examples && ...'`.
- circuitRF's command line puts the verb first: `./kit.sh circuitrf check <path>`, `circuitrf hb <file> -a <sweep>`.
- `.mcp.json` starts circuitRF's MCP server in the image with `./kit.sh circuitrf serve --root examples`. Tool
  paths are relative to `examples/`, and outputs must stay inside it.

## Checks

- `./kit.sh generator/build.sh` (about 4 min) must end with `kit built`, with `225/226 within tolerance` and
  the one known gap in circuitRF's import (even `ng` MOS drain area) in `kit/IHP_SG13G2/VALIDATION`,
  `all identical` at the end of `PCELLS`, and 0 errors from `circuitrf check`. A failed build restores the
  previous kit. Rows marked `pdk://` run the PDK's own parts as circuitRF imports them; a `gap` row is a
  difference in circuitRF's import, listed in `GAPS` in `validate_ihp_kit.py`, and turns into `ok` once
  circuitRF fixes it.
- `./kit.sh circuitrf check examples --summary` must report 0 errors. The 5 warnings are expected: `Kit_cells`
  and `inductor/schematic` declare no analysis, and the technology states no DRC rules (three layouts).
  On a fresh clone, before a build, add `--trust-kit examples/ihp-sg13g2-pcells`.
- After changing a bench, run it with the commands in `examples/README.md`. If a picture changes, regenerate
  the figures with `./kit.sh docs/make-figures.sh`.
- Before committing, search the diff for absolute paths, user names and host names.

## Conventions

- Benches place kit cells as `ws://IHP_SG13G2/<cell>`, through the `ReferencedWorkspaces` alias in the `.cws`.
  Never use a raw relative `CellRef`.
- A workspace gets the IHP PDK (its parts, corners and PCells) from `circuitrf import pdk <PDK> --into <ws>`,
  which records `PdkRefs` in the `.cws` and declares the PCells in `ihp-sg13g2-pcells/`. Do not write either
  by hand. The PDK's HBTs need the kit's VBIC 1.3 declared as `standIns` in that `PdkRefs` entry's
  `Settings` (`generator/circuitrf-ihp-workspace` adds it); its `file` is an absolute path to the built
  `vbic_1p3_5t.osdi`, so it is never committed, and a later import drops it.
- A kit cell's status and note live in `generator/qucs_cells.json`. Update it when a cell is added or fixed;
  the build prints it on `examples/Kit_cells`.
- Use relative paths only. The kit is relocatable because its cells name `models/osdi/<model>.osdi` relative to
  the kit's own `.cws`. `.cem` `LayoutRef` and load-pull grid paths are workspace-relative. The one machine path
  in a user-facing file is `PdkRefs` `/foss/pdks/ihp-sg13g2` in `examples/.cws`. The image's `/foss/...` paths
  in `kit.def` and `generator/` are expected.
- No absolute machine paths, user names or host names in committed files or pictures. circuitRF's Messages
  pane shows paths, so keep it out of screenshots.
- Figures come from `docs/make-figures.sh`. It writes `docs/images/<name>.png` and a white-background copy in
  `docs/images/white/`, which is the one the pages use.
- EM runs are long. On 16 cores the inductor takes 1 h 18 min on Palace and about 2 h on the planar MoM.
  openEMS is estimated at about 9 h, and EMerge takes 28 s. Run these in the background or as a batch job, and
  check the cost first with `circuitrf check <cem>` or `circuitrf em <cem> --dry-run`. `kit.sh` passes
  `PALACE_NP` (Palace ranks, 16 by default) and `OMP_NUM_THREADS` through to the image. EMerge installs into
  `.home/` with `./kit.sh circuitrf solver install emerge --yes`.
- The documents are written in a professional tone. They state results, not process notes.

## Licensing

- The repository and its release are Apache-2.0, like the IHP PDK. `NOTICE` lists the sources.
- Never commit or package VBIC-derived files. These are `vbic_1p3*.osdi`, `npn13G2*.osdi` (harmonicaRF's
  devices), and any copy or patched copy of VACASK's `vbic_1p3.va`. The source has no license header and VACASK
  is AGPL-3.0. `generator/build-vbic.sh` compiles these files wherever the kit is used. `kit/` is git-ignored,
  and `ci/build-release.sh` strips them from the release and fails if one is left.
- These files are fine to ship: `r3_cmc.osdi` (the PDK's own R3 CMC build), `psp103.osdi` (the PDK's PSP 103
  build; NOTICE carries its CMC statement, which a binary release must reproduce) and `models/ihp/*.va` (PDK parameter
  values, not model code).
- No GPL-3.0 material. The PDK's `libs.tech/palace` is GPL-3.0. The EM stackup comes from the Apache-2.0 ITF and
  process specification.

## Commits

- Commit only when asked. Use author `aissus <21298498+aissus@users.noreply.github.com>` and end the message with
  `Co-Authored-By: Claude Opus 5.5 (claude-opus-5-5)` (no email).
- Work forward only. Never amend, rebase or force-push pushed history.
- Record the numbers a change was checked with (validation rows, run results, times) in the commit message.
