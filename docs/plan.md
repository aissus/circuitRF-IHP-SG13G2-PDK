# circuitRF-IHP-SG13G2-PDK: plan

Drafted 2026-11-05 (set aside). Revised 2026-11-07:
- the upstream fixes the kit depends on were released in circuitRF 1.7.3;
- the kit gets an image of its own;
- the inductor is also checked with circuitRF's planar MoM;
- the README documents the flow.

## Status (2026-11-09): circuitRF 1.7.5

circuitRF 1.7.5 carries the kit's upstream pull requests #47 to #49: an OpenPDK kit's devices simulate
straight from import, a CNI PCell library runs unmodified, and a kit's settings can declare a compiled
stand-in for a built-in model card. The kit now:
- runs on 1.7.5 (`kit.def`);
- takes IHP's PCells from circuitRF's own import of the PDK (`examples/ihp-sg13g2-pcells/`, written by
  `circuitrf import pdk`), without its own patched entry: still 50 of 50 identical to KLayout;
- validates the PDK's imported parts as well as its cells, the HBTs on the kit's VBIC 1.3 declared as
  `standIns`: 225/226, plus one known gap in the import (an imported MOSFET with even `ng` gets the odd-`ng`
  drain and source areas, because circuitRF settles the PDK's `.if` on `ng` once, at `ng = 1`);
- has `generator/circuitrf-ihp-workspace` import the PDK and declare the stand-in.

The kit's own 143 rows are as on 1.7.4, except the resistors, now 0.00 % from ngspice (0.08 % before):
1.7.5's OSDI worker no longer answers `$simparam("shrink")`, which R3 read as a 1 % shrink.

## Status (2026-11-07)

Steps 0–5 and 7 are done, and step 6 (the inductor) is running; see the git log. README.md is the
record. Where the work went differently from the plan below:
- **The kit has a `.cws`.** A relative `File=` in a library cell resolves against the nearest `.cws`,
  so the cells name `models/osdi/<model>.osdi`, not `../../models/...`.
- **The examples place kit cells as `ws://IHP_SG13G2/<cell>`**, through a `ReferencedWorkspaces` alias,
  which is circuitRF's documented form. Raw relative paths are not.
- **The `.charm` check came out "regenerate".** An External DUT is identified by its absolute
  `Provider`, so `build.sh` writes the 8 documents (git-ignored).
- **The wafer is the specification's 750 µm**, not the GPL XML's 180 µm.
- **Palace:** circuitRF's own install builds from source. The image therefore wraps the base's Palace
  (the validated commit). The wrapper runs the binary under the launcher, because the base's scripts
  nest `mpirun`.
- **The inductor** is the `inductor2` PCell at its minimum opening for 5.4/4.1 µm and 2 turns (92.5 µm,
  where the old drawing was 88 µm). It keeps the old example's Metal1 ring, which was a ring, not a plane.
- **Planar MoM:** edge ports are always de-embedded, and on this substrate the calibration standards
  need 84–167 GB and an isolation the two terminals cannot have. The MoM layout therefore joins the
  terminals with a bar and drives one internal delta-gap port: differential L and Q. The test bench
  reports differential L and Q for every solver, so all four compare.

## Background

The IHP SG13G2 kit for circuitRF and its example workspaces, as a repository of their own, published as
github.com/aissus/circuitRF-IHP-SG13G2-PDK. Nothing is copied in yet. Today the kit lives beside an IIC-OSIC-TOOLS-based
Apptainer image (IIC-OSIC-TOOLS plus circuitRF):
- **Sources:** `circuitrf-kit/`.
- **Built kit:** `kits/IHP_SG13G2/`, built 2026-10-30 on a patched circuitRF 1.6.0, validation 120/120.
- **Examples:** `designs/IHP_kit_examples` and `designs/IHP_kit_demo`.

## Why a repository of its own, not a circuitRF pull request

circuitRF's `CLAUDE.md` bans the names of any PDK that does not come built into circuitRF. Its PDK guide
(`docs/user/src/reference/pdk-integration.md`) says real kits don't ship with circuitRF. The generic fixes found
while building the kit went upstream separately and are released (below).

circuitRF can already import the IHP Open PDK tree itself (File ▸ Manage Libraries: 216 parts from IHP's xschem
symbols and ngspice models). It cannot run those HBTs, though: they use ngspice's built-in VBIC, which circuitRF
does not have. This kit fills that gap. Its cells bind the PDK's own model expressions to VBIC 1.3 compiled with
OpenVAF. It also adds the IHP technology with an EM stackup.

## What changed since the first draft

- **circuitRF 1.7.3 (released 2026-11-07) carries every fix the kit needed**, so no patched build is needed:
  - `da4ede6f0`: the OSDI worker installs the `$limit` table and state vectors.
  - `a74026d68`, `0e38b41fa`, `5f6edb207` and `5cac1b02f`: the 3D view draws without GPU interop.

  Checked on main the day before the release: a VBIC operating point with the kit's `vbic_1p3_5t.osdi` converges at
  the expected V(c) = 2.731 V. The pre-merge worker dies on it. 1.7.3 is the kit's minimum.
- **Relative references resolve upstream** (traced in the source):
  - A `.cws` `LibraryRefs` / `PdkRefs` entry resolves against the workspace root (`WorkspaceRefs.Resolve`).
    `LibraryRefs` also takes `${VAR}` (`PathTokens`).
  - A VerilogA `File=` is rebased onto the document's own folder (`FileReferences.Rebase`).
  - A `.charm` names its model files document-relative (`DocumentFileRefs`).
  - Headless runs take `--kits <dir>`.

  So the files users open can carry relative paths.
- **The command line takes the verb first** (`circuitrf check …`). `circuitrf cli <verb>` was that image's own
  wrapper and does not exist upstream.

## The kit's own image

The IIC-OSIC-TOOLS-based image stays untouched, since other work uses it. The kit gets an image of its own from the **same public
base**, `hpretl/iic-osic-tools:2026.09`. That base already holds everything the generator calls:
- ngspice, Xyce and OpenVAF;
- VACASK's VBIC sources at `/foss/tools/vacask`;
- the IHP PDK at `/foss/pdks/ihp-sg13g2`, commit `c271a7e97`. That is the commit the kit was built and validated
  from: the sandbox's `PDKs/` is a copy of this base's PDK.

So the image only adds circuitRF 1.7.3 from the release tarball, which ships its `osdi-worker` beside the app.
`kit.def`, in this repo:

```text
Bootstrap: docker
From: hpretl/iic-osic-tools:2026.09

%environment
    export HWLOC_COMPONENTS=-gl                       # MPI tools hang probing X displays
    export CRF_VERILOGA_COMPILER=/foss/tools/bin/openvaf

%post
    set -eux
    # The kit is generated from, and validated against, this PDK commit.
    test "$(cat /foss/pdks/ihp-sg13g2/COMMIT)" = c271a7e97a7bab201c1d0a399215969d2ee19573
    curl -fsSL https://github.com/potatobeanradio/circuitRF/releases/download/1.7.3/circuitRF-1.7.3-linux-x64.tar.gz \
        | tar -xz -C /opt
    ln -s /opt/circuitRF-1.7.3/app-1.7.3/circuitRF /usr/local/bin/circuitrf
    circuitrf --version                                # fails the build if the runtime is short of a library
```

- **Building it:** `APPTAINER_CACHEDIR=<own cache> apptainer build --fakeroot kit.sif kit.def`, the way the IIC-OSIC-TOOLS-based
  image is built. The image is about 5 GB (git-ignored).
- **`kit.sh <cmd…>`:** a launcher in the style of `dev.sh`. It runs `apptainer exec --cleanenv` on `kit.sif`, with
  the repo bound and a `.home/` of its own (git-ignored).
- **Before the first build, check** that `PDKPATH` is set under `--cleanenv`, as `run.sh` relies on. If not,
  `kit.sh` exports it.
- **Bumping circuitRF or the PDK** means editing this def: one URL, or the base tag plus the `COMMIT` check. Then
  rebuild and revalidate.
- **Inductor step only:** circuitRF's 3D EM wants the Palace it validated. The IIC-OSIC-TOOLS-based image wraps the base's
  Palace for that (its recipe's `$C/palace` script), and the kit image takes the same wrapper only if that step
  needs it. openEMS is in the base; EMerge installs into `.home` with `circuitrf solver install emerge`.

## Layout

```text
generator/   <- circuitrf-kit/* (build.sh, ihp2crf.py, ihp2va.py, qucs2csym.py, harmonica_ihp.py,
                validate_ihp_kit.py, va2cnl.py, circuitrf-ihp-workspace)
examples/    <- ONE workspace: designs/IHP_kit_examples + the CE_10GHz_HB cell from designs/IHP_kit_demo
kit/         <- build output of generator/build.sh, git-ignored (holds compiled .osdi, see Licensing)
kit.def  kit.sh  README.md  LICENSE (Apache-2.0)  NOTICE  .gitignore  PLAN.md
```

`.gitignore`: `kit/`, `*.sif`, `.home/`, `results/`, `.generated-cells/`, `.cwsuser`.

Examples to keep:
- **Qucs-S ports:** HBT_Ic, HBT_IcVce, HBT_fT_fmax, Resistors, MIM_Cap.
- **Load-pull:** HBT_Loadpull, plus the 8 harmonica `.charm` documents.
- **EM:** inductor (EM) and inductor_TB (L/Q from all solvers).
- **From the demo:** CE_10GHz_HB.

Leave out (not sources, machine-local, or duplicates):
- **Machine-local:** `results/`, `.generated-cells/`, `.cwsuser`.
- **One-off script:** `compare_Nx8.py` (container-only).
- **Duplicate:** `inductor/3d/inductor2.c3d` (a copy of `inductor.c3d`).
- **GPL-3.0 output:** `inductor/gds2palace/`.
- **From the demo:** the stray cell `hhhh/`, the bare `netlist.cnl`, and the duplicate `tech/` and `harmonica/`.

## Paths

The generator runs only in `kit.sif`, so its `/foss/...` tool and PDK paths are the image's own and stay. What
changes is every path that ends up in a file a user opens, plus the output location:

| What | Today | Becomes |
|---|---|---|
| kit cells' model `File=` (`npn13G2{,l,v}`, `rsil`/`rppd`/`rhigh`) | `/foss/tools/circuitrf/kits/…/models/osdi/*.osdi` | `ihp2crf.py` writes it relative to the cell, e.g. `../../models/osdi/vbic_1p3_5t.osdi`. The `--osdi` argument goes; the built kit is then relocatable. |
| `.cws` `LibraryRefs` (`IHP_kit_examples/.cws:4`, demo `.cws:4`) | `/foss/tools/circuitrf/kits/IHP_SG13G2` | `../kit/IHP_SG13G2` |
| example `CellRef`s (`HBT_*`, `MIM_Cap`, `Resistors.csch:77,140,203`, `CE_10GHz_HB.csch:25`) | absolute, or ten `../` | relative to `../kit/IHP_SG13G2` (a `CellRef` never takes `${VAR}`, by design) |
| `.charm` `ModelFile` (line 8) and `Provider` (line 6) | absolute | `harmonica_ihp.py charm` writes `ModelFile` relative. **Check first:** `Provider` is `VerilogA\|<absolute path>`. If circuitRF re-derives it from `ModelFile` on open, the 8 documents are committed; if not, they are regenerated by `build.sh` and git-ignored. |
| `.cws` `PdkRefs` | `/foss/pdks/ihp-sg13g2` | Stays: the PDK's path in both images, documented as the one machine path. `PdkRefs` takes no `${VAR}`. Only `HBT_layout` and the palette need it. |
| `build.sh:12` `K=` | `/foss/tools/circuitrf/kits/IHP_SG13G2` | `<repo>/kit/IHP_SG13G2`; the "kits/ is not mounted" check goes |
| `circuitrf cli <verb>` (`build.sh` check and `--version`, `validate_ihp_kit.py:62`) | that image's wrapper form | `circuitrf <verb>` |
| usage text: `ihp2crf.py:4`, `validate_ihp_kit.py:4,251`, `circuitrf-ihp-workspace:14-15`, `build.sh:2-8` | `run.sh` and `/foss/tools/circuitrf/kits` | `./kit.sh …` and repo paths |
| examples `README.md:3,25,36,62,172` | `/foss/...` and `run.sh` | repo-relative, and `./kit.sh` |

## Licensing

- **Repository:** Apache-2.0, the same as the IHP PDK.
- **NOTICE** credits:
  - the IHP PDK Authors (Apache-2.0): model expressions, layer table, ITF stackup, inductor PCell geometry;
  - the Qucs-S `user_lib` symbols (Mike Brinson);
  - R3 CMC (ECL-2.0, Si2), in the built kit only;
  - VBIC 1.3 from VACASK, in the built kit only.
- **VBIC-derived `.osdi` files are built, never committed.** The `vbic_1p3.va` in VACASK has no license header and
  VACASK is AGPL-3.0, so the repo carries only the scripts that build them. That is why `kit/` is git-ignored.
- **No GPL-3.0 material.** The PDK's `libs.tech/palace` is GPL-3.0. Today it supplies the `.ctech` EM stackup
  (`workflow/SG13G2_200um.xml`), the inductor GDS and the gds2palace `.s2p`. Both get replaced:
  - **Stackup:** `ihp2crf.py`'s tech step (`ihp2crf.py:408-467`) reads `libs.tech/parasitics/itf/sg13g2_typ.itf`.
    That file is Apache-2.0 and gives per-layer THICKNESS, ER and RPSQ; σ = 1/(RPSQ·t). Substrate and EPI values
    come from `libs.doc/doc/SG13G2_os_process_spec.pdf`, cited in a comment. Print the old and new z-positions
    side by side once as a sanity check.
  - **Inductor:** drawn from IHP's Apache KLayout PCell (`sg13g2_pycell_lib/ihp/inductors_code.py`) at the old
    500 pH geometry:
    1. Write a GDS with the base's KLayout.
    2. `circuitrf import` it into `examples/inductor/layout`, and redraw the two ports.
    3. Run Palace, openEMS and EMerge once, Palace as a batch job if it is slow. L should agree with the old run within
       a few %. No tuning.
    4. **circuitRF's own planar MoM** on the same layout and stackup. Planar is the `.cem` default, so the setup
       is the 3D one without `Solver3D`; `check` says whether it wants planar ports instead of `Ports3D`.
       - It takes seconds per point, so it covers the whole sweep.
       - Its L and Q go in the same table as the 3D solvers. It reads the stackup layer by layer, so it is also a
         check of the ITF-derived stackup.
       - Where it disagrees with Palace, the MoM reference's limits (a sheet conductor model, laterally infinite
         layers) are named rather than tuned away.
- **`kit.def`** names a public base and a public release; nothing from either is committed.

## Steps

0. **GitHub (user):** create an empty `aissus/circuitRF-IHP-SG13G2-PDK`, with no README or license so the first
   push is clean. Locally, the folder is already `circuitRF-IHP-SG13G2-PDK`, and it holds one commit (this plan).
   Commits are `aissus <>` with the model-name trailer.
1. **Image:**
   - write `kit.def` and `kit.sh`, and build `kit.sif`;
   - `./kit.sh circuitrf --version` prints 1.7.3;
   - `./kit.sh bash -c 'echo $PDKPATH'` prints the PDK.
2. **Generator as-is:** copy `circuitrf-kit/*` into `generator/` unchanged. Commit, so history shows the starting
   point.
3. **Generator in the repo:**
   - the path table's generator rows: output to `kit/`, relative model `File=`, verb-first CLI;
   - `./kit.sh generator/build.sh`;
   - the cells must pass `circuitrf check` from a second location, which proves the relative `File=`.
4. **Stackup from the ITF.** Apache-2.0 replaces the GPL XML. Check the z-positions once.
5. **Examples:**
   - copy the kept ones, with the relative `LibraryRefs` and `CellRef`s;
   - do the `.charm` `Provider` check (commit or regenerate);
   - write `.gitignore`.
6. **Inductor redrawn** from the Apache PCell, with one run each of Palace, openEMS, EMerge and circuitRF's planar
   MoM.
7. **README, LICENSE, NOTICE.** The README documents the flow end to end:
   - image, generator scripts in order, `kit/`, validation, examples;
   - what each script reads from the PDK and what it writes;
   - what is checked, and against what;
   - what the kit is;
   - circuitRF ≥ 1.7.3;
   - build the image, then the kit (two commands);
   - the `PdkRefs` machine path;
   - opening the examples with any circuitRF ≥ 1.7.3.
8. **Verify** (below), then the user pushes: `git -c credential.helper= push -u origin main`.

## Verification

All of it runs in `kit.sif`:
- `generator/build.sh`: validation 120/120 against ngspice and Xyce, and `circuitrf check` on every cell, on 1.7.3.
- `circuitrf check --kits kit` on every example bench.
- The VBIC operating point from 2026-11-06 (V(c) = 2.731 V) through a kit cell.
- CE_10GHz_HB once, compared with the sandbox's `designs/IHP_kit_demo/results`.
- The inductor's L and Q from the planar MoM against Palace and the old gds2palace numbers.
- A search of the committed tree for absolute paths (home and project directories, host names, `/foss` outside
  `kit.def` and `generator/`) finds only the documented `PdkRefs`.

## Not in this plan

- **In the IIC-OSIC-TOOLS-based image, at its next rebuild** (see `docs/iic-osic-tools-integration.md`):
  - move it to circuitRF ≥ 1.7.3 and drop the two `recipe/circuitRF/*.patch`;
  - if wanted, build the kit from this repo instead of `circuitrf-kit/`.
- **Repackaging as a vendor model library** (`library.clib` / `part.cpart`, per-platform `models/<rid>/`): the cell
  kit works and validates. Revisit only if a non-Linux user needs it.
- **Noise analysis** and **native VBIC:** not now (OSDI is upstream's way).
