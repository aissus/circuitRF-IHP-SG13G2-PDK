# Using the kit in an IIC-OSIC-TOOLS-based image

A plan, not yet carried out.

The [IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) Docker image
(`hpretl/iic-osic-tools`, tag 2026.09) is the base of this repository's kit image. It is also the base
of an Apptainer image with circuitRF added: its recipe (`*.def`), its setup script (`setup.sh`) and its
launcher (`run.sh`). That image builds its own copy of this kit, from an older copy of `generator/`.

This plan moves that image to the kit as this repository releases it: compiled and validated by
`.github/workflows/release.yml`, and published as `circuitRF-IHP-SG13G2-<tag>.zip` with a `.sha256`. The
archive holds one folder with `kit/IHP_SG13G2/`, the example workspace, `generator/`, `LICENSE` and
`NOTICE`. The release is Apache-2.0 throughout, so it does not carry the VBIC models: the image compiles
them once, with its own OpenVAF (`generator/build-vbic.sh`). The image then no longer builds the kit.

## Where things stand

| | IIC-OSIC-TOOLS-based image, today | Kit image (`kit.sif`, from `kit.def`) |
|---|---|---|
| Base | IIC-OSIC-TOOLS 2026.09, PDK commit `c271a7e97a7b…` | the same, so the same PDK, OpenVAF, ngspice, Xyce and Palace |
| circuitRF | 1.6.0, built from source in the recipe (.NET SDK), GUI and CLI as two programs | 1.7.3, the release tarball: one program |
| Patches to circuitRF | two: the OSDI worker's `$limit` and state (without it, VBIC crashes), and the 3D view's software present | none: both are upstream since 1.7.3 |
| Command line | `circuitrf cli <verb>` (the recipe's wrapper) | `circuitrf <verb>` (upstream) |
| Kit built by | the setup script, after every image build, from `circuitrf-kit/` | `generator/build.sh`; released by the workflow |
| Kit location | host `kits/IHP_SG13G2`, mounted by `run.sh` at `/foss/tools/circuitrf/kits/IHP_SG13G2` | `kit/IHP_SG13G2`, or anywhere once unpacked |
| Model paths in the cells | absolute: `/foss/tools/circuitrf/kits/IHP_SG13G2/models/osdi/…` | `models/osdi/<model>.osdi`, relative to the kit's own `.cws` |
| Workspaces place a cell as | `/foss/tools/circuitrf/kits/IHP_SG13G2/<cell>` | `ws://IHP_SG13G2/<cell>`, through a `ReferencedWorkspaces` alias plus a `LibraryRefs` entry |
| Kit `tools/` | a copy of the generator. The image links `/foss/tools/circuitrf/tools` and `circuitrf-ihp-workspace` into it | none; the generator is `generator/` here |
| EM stackup (`tech/IHP_SG13G2.ctech`) | from the PDK's gds2palace XML (GPL-3.0); 180 µm substrate | from the PDK's ITF and process specification (Apache-2.0); 750 µm substrate |
| Validation | 120/120 on circuitRF 1.6.0 | 120/120 on 1.7.3, every number the same |
| Palace wrapper, solve branch | its own `run_palace` (`PALACE_NP` cap, error estimate off) → Palace's `palace` launcher → one `mpirun` | `<launcher> -n N palace-x86_64.bin config.json` directly, with the `PALACE_NP` cap |
| EMerge | installed into the image by circuitRF's installer; the wrapper hard-codes `emerge/3.0.0b3/env` | installed per user; circuitRF 1.7.3 pins EMerge **3.0.0** |
| harmonicaRF `.charm` | in an example workspace, naming the kit's `.osdi` by absolute path | written by `generator/build.sh` into `examples/harmonica/` (git-ignored, not in the release) |

The cells themselves are the same. Between the two builds, each cell's schematic differs only in its
model path. Cell names, pins and parameters are unchanged.

## Recommended: the released kit

### 1. circuitRF 1.7.3 in the recipe

There are two ways:

- **A. Keep building from source** at tag `1.7.3`, and drop both patches. This is the **smaller diff**:
  one tag changes and the patch lines go. 1.7.3 still has both `src/Ui` and `src/Cli` and still targets
  .NET 10, so the rest of the build block stands.
- **B. Install the release tarball, as `kit.def` does.** This is a bigger diff, because the whole .NET
  block goes. It leaves a **smaller recipe**, and it is the recommendation:
  - it is the binary the kit was validated on;
  - the build fetches neither a .NET SDK nor NuGet packages;
  - it ships the OCCT geometry kernel and the gdstk worker, which the source build skips;
  - the next bump is one URL;
  - from 1.7.3 on, the app runs the verbs itself, so one program serves both the GUI and the CLI.

Proposed change to the recipe for B:

```diff
 %files
-    circuitRF/osdi-worker-limit-and-state.patch /opt/crf.patch
-    circuitRF/viewer3d-software-present.patch /opt/crf-viewer3d.patch
     circuitRF/osdilibs /foss/tools/circuitrf/models/osdi

 %environment
     export HWLOC_COMPONENTS=-gl
+    # circuitrf-ihp-workspace: where run.sh mounts the kit
+    export IHP_KIT=/foss/tools/circuitrf/kits/IHP_SG13G2

 %post
     ...
     apt-get update
-    apt-get install -y --no-install-recommends dotnet-sdk-10.0
-    export DOTNET_CLI_HOME=/opt/build/dn NUGET_PACKAGES=/opt/build/nuget CC=gcc \
-           DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
-    git clone --depth 1 --branch 1.6.0 https://github.com/potatobeanradio/circuitRF /opt/build/crf
-    cd /opt/build/crf
-    patch -p0 tools/osdi-worker/osdi_worker.c < /opt/crf.patch
-    patch -p1 < /opt/crf-viewer3d.patch
-    dotnet publish src/Ui/CircuitRF.Ui.csproj   ... -o $C/app
-    dotnet publish src/Cli/CircuitRF.Cli.csproj ... -o $C/cli
-    cp $C/app/osdi-worker $C/cli/
-    cp -n $C/app/*.so $C/cli/
+    # circuitRF's release: one self-contained program for the GUI and the verbs, its osdi-worker beside it.
+    curl -fsSL https://github.com/potatobeanradio/circuitRF/releases/download/1.7.3/circuitRF-1.7.3-linux-x64.tar.gz \
+        | tar -xz -C /opt
+    ln -s /opt/circuitRF-1.7.3/app-1.7.3 $C/app
     ...
-    HOME=$C/solver-home $C/cli/CircuitRF.Cli solver install emerge --yes
+    HOME=$C/solver-home $C/app/circuitRF solver install emerge --yes
     ...  (the circuitrf wrapper)
-E=$C/solver-home/.local/share/circuitRF/solvers/emerge/3.0.0b3/env
+E=$C/solver-home/.local/share/circuitRF/solvers/emerge/3.0.0/env
 bin=$C/app/circuitRF
-[ "$1" = cli ] && { shift; bin=$C/cli/CircuitRF.Cli; }
+[ "$1" = cli ] && shift     # `circuitrf cli <verb>` stays for existing scripts; the app runs verbs itself
     ...
-    apt-get purge -y dotnet-sdk-10.0 qtbase5-dev ...
+    apt-get purge -y qtbase5-dev ...
-    rm -rf /opt/build /opt/crf.patch /opt/crf-viewer3d.patch /opt/run_palace ...
+    rm -rf /opt/build /opt/run_palace ...
```

`mkdir -p /opt/build` stays, because EMStudio's build still uses it.

Option A changes the same `%files`, `IHP_KIT` and EMerge lines, sets `--branch 1.7.3`, and deletes the
two `patch` lines. In both options, the patch files in the recipe's folder can then be deleted.

**The EMerge path has to change either way.** circuitRF 1.7.3 installs EMerge 3.0.0 into `…/emerge/3.0.0/env`,
and `lib/libmkl_rt.so.3` is still in it. With the old `3.0.0b3` path, the recipe's own
`circuitrf cli solver list` check would report EMerge not found and stop the build.

The image's 45 compact models in `/foss/tools/circuitrf/models/osdi` are not part of the kit, so they
stay as they are.

### 2. Fetching the kit in the setup script

Step 3b today rebuilds the kit whenever the image is newer than the kit. Proposed replacement:

```bash
# 3b. The IHP SG13G2 kit for circuitRF, compiled and validated by circuitRF-IHP-SG13G2-PDK's release;
#     run.sh mounts kits/ at /foss/tools/circuitrf/kits. To change release: set both lines, delete
#     kits/IHP_SG13G2, re-run.
KIT_TAG=v1.0.0                              # the release to use
KIT_SHA256=<the hash in that release's .sha256>
mkdir -p kits designs   # run.sh mounts both
if step kits/IHP_SG13G2; then
    R=https://github.com/aissus/circuitRF-IHP-SG13G2-PDK
    n=circuitRF-IHP-SG13G2-$KIT_TAG
    T=$(mktemp -d)
    curl -fsSL -o "$T/$n.zip" "$R/releases/download/$KIT_TAG/$n.zip"
    echo "$KIT_SHA256  $T/$n.zip" | sha256sum -c -
    unzip -q "$T/$n.zip" -d "$T"
    mv "$T/$n/kit/IHP_SG13G2" kits/
    # The release's generator/ becomes the kit's tools/, where the image's
    # /foss/tools/circuitrf/tools and circuitrf-ihp-workspace links point.
    cp -r "$T/$n/generator" kits/IHP_SG13G2/tools
    rm -rf "$T"
    # The VBIC models are not distributed: compile them with the image's OpenVAF, and with its PDK
    # also harmonicaRF's devices.
    ./run.sh /foss/tools/circuitrf/kits/IHP_SG13G2/tools/build-vbic.sh /foss/tools/circuitrf/kits/IHP_SG13G2
fi
grep -qx "PDK commit $(cat PDKs/ihp-sg13g2/COMMIT)" kits/IHP_SG13G2/BUILD ||
    { echo "kits/IHP_SG13G2 was built from another PDK than the image's (see its BUILD)" >&2; exit 1; }
```

- **Pin the hash, don't download the `.sha256`.** A `.sha256` fetched from the same release only shows
  that the download is complete. A pinned hash also shows that it is the archive you checked.
- **The archive's version is the tag itself.** `ci/build-release.sh` names it from `git describe`, so it
  is `circuitRF-IHP-SG13G2-v1.0.0.zip`, with the `v`.
- **The release does not depend on the image build.** It no longer has to be redone when the image is
  rebuilt. Only the PDK commit ties the two together, and the `grep` above checks it.

**Switching once.** `kits/IHP_SG13G2` exists today, so the step above would skip it:

1. Build the new image under a new name, next to the one in use.
2. When no container of the old image is running, swap the `.sif`. On NFS, a `.sif` replaced while a
   container still has it open lingers as a hidden `.nfs…` file until that container exits.
3. Move the old kit out of `kits/`, for example `mkdir -p old && mv kits/IHP_SG13G2 old/IHP_SG13G2-circuitRF-1.6.0`.
   Out of `kits/` it is a record that nothing resolves into.
4. Run `./setup.sh`.

`circuitrf-kit/` is then unused. Don't run its `build.sh` against `kits/IHP_SG13G2` again: it would put
back a kit with absolute paths and no `.cws`, and the alias in new workspaces would stop resolving.

### 3. The mount: keep `/foss/tools/circuitrf/kits`

The released kit needs no particular path. Its cells name their models relative to the kit's `.cws`,
so it works wherever it is unpacked. A second copy is independent: for example, the next release
unpacked as `kits/IHP_SG13G2-v1.1.0` beside the current one runs its own models. With the old kit, a
second copy silently ran the first copy's models.

What still needs the path is everything that points at the kit from outside:

- **Existing workspaces, netlists and scripts.** About 240 files in the current `designs/` name
  `/foss/tools/circuitrf/kits/IHP_SG13G2/…`, most of them generated `.cnl` netlists that name the
  kit's `.osdi` files. List them with `grep -rlI /foss/tools/circuitrf/kits designs/`.
- **The recipe's two links into the kit:** `/foss/tools/circuitrf/tools` → `kits/IHP_SG13G2/tools`, and
  `models/osdi/vbic_1p3_bce.osdi`. The setup step above restores `tools/`, and `build-vbic.sh` makes that file.
- **Existing `.charm` documents.**

So `run.sh` stays as it is. Relocatability still buys several things:

- the host folder is a plain unpacked archive;
- nothing is rebuilt after an image rebuild;
- versions can sit side by side;
- new workspaces survive a move by editing two paths in their `.cws`.

### 4. Workspaces

- **New workspaces:** run `circuitrf-ihp-workspace my_project` in the image, or `bin/circuitrf-ihp-workspace`
  from the host. This is now this repository's `generator/circuitrf-ihp-workspace`, and it reads `IHP_KIT`
  from the recipe's `%environment`. Without `IHP_KIT` it looks for `../kit/IHP_SG13G2` next to its own
  folder and fails there. The workspace it makes has these:
  - `LibraryRefs` and the `IHP_SG13G2` alias, both on `/foss/tools/circuitrf/kits/IHP_SG13G2`;
  - `PdkRefs` on `/foss/pdks/ihp-sg13g2`;
  - its own copy of the new 750 µm technology.

  Cells are placed as `ws://IHP_SG13G2/<cell>`.
- **Existing workspaces keep working unchanged** while the kit stays at
  `/foss/tools/circuitrf/kits/IHP_SG13G2`, because the cells keep their names, pins and parameters. They
  also keep their own copy of the old technology (see Risks).
- **Migrating to the alias** is only worth doing if the kit will move, or if a workspace will be opened
  outside this image. Do it under version control, or after a backup:

  ```bash
  cd designs
  # 1. Each .cws that references the kit gains the alias; its LibraryRefs entry stays.
  grep -rlI --include=.cws /foss/tools/circuitrf/kits/IHP_SG13G2 . | while read -r f; do
    python3 - "$f" <<'EOF'
  import json, sys
  p = sys.argv[1]; w = json.load(open(p))
  refs = w.setdefault('ReferencedWorkspaces', [])
  if not any(r.get('Alias') == 'IHP_SG13G2' for r in refs):
      refs.append({'Alias': 'IHP_SG13G2', 'Path': '/foss/tools/circuitrf/kits/IHP_SG13G2/.cws'})
  json.dump(w, open(p, 'w'), indent=2)
  EOF
  done
  # 2. Cell references, absolute or behind a run of ../, become the alias.
  grep -rlI --include=*.csch /foss/tools/circuitrf/kits/IHP_SG13G2/ . | xargs -r sed -i -E \
    's#"CellRef": "(\.\./)*/?foss/tools/circuitrf/kits/IHP_SG13G2/#"CellRef": "ws://IHP_SG13G2/#'
  ```

  Then run `circuitrf check` on each migrated schematic. The alias needs the new kit, because the old
  one has no `.cws`.
- **Netlists and scripts** that name `…/models/osdi/*.osdi` have no alias form. They keep working at the
  fixed path. If the kit ever moves, change the path in the script that writes them, then regenerate.

### 5. The `circuitrf cli` form

Keep it. The wrapper line in step 1 makes both forms work:

- `circuitrf <verb>` is what this repository's scripts and upstream use.
- `circuitrf cli <verb>` is what existing scripts, batch jobs and the MCP server entry (`circuitrf cli serve`) use.

Dropping `cli` buys nothing.

### 6. The Palace wrapper: no change needed

This conclusion comes from reading the scripts; nothing was run.

**What hit this repository.** `kit.def`'s first wrapper handed the solve to the **base's** `run_palace`. That
script runs `mpirun -np N palace`, where `palace` is Palace's own launcher script, which starts `mpirun`
again. Palace stopped with `mpirun does not support recursive calls`.

**Why the recipe's wrapper is not affected:**

- The recipe copies its own `run_palace` over the base's, and that one runs the launcher once:
  `exec /foss/tools/palace/bin/palace -np "$NP" "$CONFIG"`. The chain therefore has a single `mpirun`.
- circuitRF 1.7.3 starts Palace as 1.6.0 did. It runs `<CIRCUITRF_PALACE> -np N --launcher <mpirun> config.json`
  and does not run that program under MPI itself (`PalaceCommand` in circuitRF's
  `src/Design/Em3d/PalaceRun.cs` is the same in both).
- 1.7.3 still validates Palace commit `0dc74cd`, so the `--version` branch stays as it is.

Keep that wrapper. It also has the error-estimate saving that `kit.def`'s wrapper lacks. It would nest
`mpirun` only if the recipe stopped installing its own `run_palace`. In that case, take `kit.def`'s
solve line:

```bash
    exec "$4" -n "$n" /foss/tools/bin/palace-x86_64.bin "$5"
```

### 7. That image's documentation

Several statements in it become out of date:

- "circuitRF 1.6.0";
- the worker-patch and 3D-view-patch paragraphs (both fixes are upstream in 1.7.3, and Settings ▸
  Appearance ▸ *Software 3D without GPU interop* is on by default);
- "two optional helpers aren't built", which no longer holds with option B;
- the kit build instructions (`circuitrf-kit/build.sh`);
- the recipe's header comment about `circuitRF/`.

## Alternative: build the kit inside the image

This takes the repository's generator and needs circuitRF ≥ 1.7.3 in the image, because
`generator/build.sh` and `generator/validate_ihp_kit.py` call `circuitrf <verb>`:

```bash
git clone -q --depth 1 --branch <tag> https://github.com/aissus/circuitRF-IHP-SG13G2-PDK repos/circuitRF-IHP-SG13G2-PDK
./run.sh bash -c 'K=/foss/tools/circuitrf/kits/IHP_SG13G2 repos/circuitRF-IHP-SG13G2-PDK/generator/build.sh &&
  cp -r repos/circuitRF-IHP-SG13G2-PDK/generator /foss/tools/circuitrf/kits/IHP_SG13G2/tools'
```

- **Always pass `K=`.** Without it, the build writes into `<checkout>/kit/`, which is not mounted.
- **Copy `tools/` after every build.** `build.sh` makes a fresh kit without `tools/`, so the image's links
  dangle until the copy runs.
- **What it does:** about a minute, with the same validation and `circuitrf check`. The previous kit is
  kept if anything fails. It also writes the harmonicaRF `.charm` documents for this kit path into the
  checkout's `examples/harmonica/`.

Prefer this path in four cases:

- **PDK bump:** the IIC-OSIC-TOOLS tag moves before a kit release for it exists. The `BUILD` check in
  step 2 stops the setup script in that case.
- **Local generator changes:** trying a generator change before it is released.
- **Licensing:** you would rather compile the VBIC-derived models locally than download them (see Risks).
- **harmonicaRF:** you want the `.charm` documents.

To make this path the setup script's default, keep the old "rebuild when the image is newer than
`BUILD`" logic around these two lines.

## Compatibility and verification

**Compatibility:**

- The `PDK commit` line in the kit's `BUILD` must equal `$PDKPATH/COMMIT` in the image (on the host,
  `PDKs/ihp-sg13g2/COMMIT`). It does as long as the recipe's `From:` and `kit.def`'s `From:` name the
  same IIC-OSIC-TOOLS tag, today 2026.09 with commit `c271a7e97a7bab201c1d0a399215969d2ee19573`.
- circuitRF ≥ 1.7.3: earlier versions crash on VBIC without the patch. The `BUILD` file also records
  the circuitRF the kit was validated on.

**After the change**, from the image's folder:

```bash
./run.sh circuitrf --version                 # 1.7.3
./run.sh circuitrf solver list               # Palace 0.18.1 (0dc74cd) validated; EMerge, openEMS, Gmsh found
K=/foss/tools/circuitrf/kits/IHP_SG13G2
./run.sh bash -c "python3 $K/tools/validate_ihp_kit.py --kit $K | diff - $K/VALIDATION"   # 143/143, no diff
./run.sh circuitrf check $K --summary
```

**The examples**, checked against the released kit in a scratch checkout under `designs/` (which the image
sees as `/foss/designs`):

```bash
git clone -q --depth 1 --branch <tag> https://github.com/aissus/circuitRF-IHP-SG13G2-PDK designs/kit-check
ln -s /foss/tools/circuitrf/kits designs/kit-check/kit     # the examples look for ../kit/IHP_SG13G2
mkdir designs/kit-check/examples/tech && cp kits/IHP_SG13G2/tech/IHP_SG13G2.ctech designs/kit-check/examples/tech/
./run.sh bash -c 'cd /foss/designs/kit-check/examples &&
  for f in */schematic/*.csch; do circuitrf check "$f" || exit 1; done &&
  circuitrf hb CE_10GHz_HB/schematic/CE_10GHz_HB.csch -a SW -o results/CE_10GHz_HB.npy &&
  circuitrf em inductor/em/inductor_emerge.cem'
```

- **One bench:** `CE_10GHz_HB` should give the same Pout, Gt, H2 and H3 as the same bench run on the old
  image. This repository found every number identical between 1.6.0 and 1.7.3. Rerun one existing design
  of your own as well, and compare it with its results from before the switch.
- **EMerge:** the run takes about 28 s and checks the new 3.0.0 path and `EMERGE_PARDISO_PATH`.
- **Palace:** start `circuitrf em inductor/em/inductor_palace.cem`, or any smaller `.cem`. Its log
  should show N ranks starting, with no `recursive calls`. The full inductor run takes about 1 h 18 min
  on 16 ranks; the failure would show in the first second.
- **3D view:** on the remote desktop, `./run.sh circuitrf designs/kit-check/examples/.cws`, open
  `inductor/layout/inductor.clay` and choose Design ▸ 3D view. It should draw, and Messages should say it
  draws in software. This is what the dropped patch used to do.

## Risks and open questions

- **Old EM results:**
  - Existing workspaces own a copy of the old technology (gds2palace XML, 180 µm substrate). New ones get
    the ITF-based stackup with a 750 µm wafer.
  - EM results from the two are not comparable.
  - To move a workspace over, copy `kits/IHP_SG13G2/tech/IHP_SG13G2.ctech` over its `tech/` copy and rerun
    its EM.
  - For a thinned die in a new workspace, edit the Substrate row of its copy.
  - The old copies derive from GPL-3.0 data, which matters only if such a workspace is published.
- **Circuit results:** the kit gives identical numbers. circuitRF 1.7.3's load-pull engine converges 5
  more of the example's 1,568 points and agrees within 0.09 dB where both converged. Other changes
  between 1.6.0 and 1.7.3 show up only by rerunning the designs that matter.
- **harmonicaRF `.charm`:** a document identifies its DUT by the `.osdi`'s absolute path. Existing
  documents name `/foss/tools/circuitrf/kits/IHP_SG13G2/models/osdi/<device>.osdi`. They work while the
  kit stays there, and `build-vbic.sh` writes the same file names. The release carries no `.charm`. Make new
  ones with `tools/harmonica_ihp.py charm <out> --device … --osdi $K/models/osdi/<device>.osdi`, and
  always pass `--osdi`, because the default looks for `../kit/`.
- **The VBIC models** (`vbic_1p3_5t.osdi`, and for harmonicaRF `vbic_1p3_bce.osdi` and `npn13G2{,l,v}.osdi`)
  are compiled in the image by `build-vbic.sh` from VBIC 1.3's Verilog-A source, which IIC-OSIC-TOOLS
  carries at the commit the script pins. The kit's validation uses the same script, so the models match
  the validated ones. Rerun it after an image rebuild that changes OpenVAF.
- **A PDK bump** means a new kit release built on the new base (`kit.def`'s `From:` and `COMMIT` check),
  or the alternative path. Until then, the `BUILD` check stops the setup script.
- **Not run:** none of the above was executed in that image. The Palace and EMerge conclusions come from
  reading its recipe, the base's scripts and circuitRF's source. The verification steps above are the
  check.
