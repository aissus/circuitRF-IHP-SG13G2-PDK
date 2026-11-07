---
name: ihp-sg13g2-kit
description: Design and simulate circuits on IHP SG13G2 (130 nm SiGe BiCMOS) in circuitRF with the circuitRF-IHP-SG13G2 kit. Covers the SG13G2 HBTs (npn13G2, npn13G2l, npn13G2v), MOSFETs (sg13_lv_nmos, sg13_lv_pmos, sg13_hv_nmos, sg13_hv_pmos), poly resistors (rsil, rppd, rhigh), MIM capacitors (cap_cmim), on-chip inductors and EM on the SG13G2 stackup. Use it to set up a workspace on the kit, place kit cells in a schematic or netlist, choose analyses (DC/I-V, S-parameters, fT/fmax, harmonic balance, load-pull) or EM solvers, drive circuitRF's MCP tools, or fix an HBT run that fails for a missing VBIC model.
---

# IHP SG13G2 kit for circuitRF

## Where things are

- **Kit:** `kit/IHP_SG13G2/` holds one folder per cell (`.ccell`, schematic, symbol, `README.md`),
  `tech/IHP_SG13G2.ctech` and `models/osdi/`. Do not edit it.
- **Examples:** `examples/` is a workspace with a working bench for each task (see the table at the end).
  Copy from these benches.
- **Commands:**
  - Release (the unzipped folder): `circuitrf <verb> ...`, from your own circuitRF 1.7.3 or newer.
  - Repository: `./kit.sh circuitrf <verb> ...`. It runs in the image and starts in the top folder, so give
    paths relative to the top folder.
  - The verb always comes first.
- **MCP server root:** the unzipped folder in a release, and `examples/` in the repository. Every tool path is
  relative to the root, and outputs must stay inside it.

## The HBTs need their VBIC model (once)

The HBT cells run `kit/IHP_SG13G2/models/osdi/vbic_1p3_5t.osdi`. The release does not ship it (licensing). If it
is missing, `check` and every run fail with:

    There is no build of 'vbic_1p3_5t.osdi' for linux-x64: neither '.../models/osdi/linux-x64/vbic_1p3_5t.osdi' nor '.../models/osdi/vbic_1p3_5t.osdi' exists

To fix it, run `generator/build-vbic.sh` once from the top folder:
- It needs `openvaf` on `PATH`, or `OPENVAF=/path/to/openvaf`.
- It compiles VBIC 1.3 from its public source.
- With `PDKPATH` set (IIC-OSIC-TOOLS), it also builds harmonicaRF's devices `npn13G2{,l,v}.osdi`.

Resistors, `cap_cmim`, the technology and EM work without it. In the repository, `generator/build.sh` runs it.

## The cells

The pins below are in netlist order. Lengths are in metres (`10u`, `10e-6`). `T` is in °C (default 27, the PDK
nominal). `dtemp` and `trise` are offsets in K. `corner` is 0 typ, 1 bcs, 2 wcs.

| Cell | Pins | Parameters (default) | PDK validity / notes |
|---|---|---|---|
| `npn13G2` | c b e bn | Nx=1 corner=0 T=27 dtemp=0 selft=1 | Nx 1–10 (emitter 0.07×0.9 µm² each). VBE 0.65–0.96 V, VCE 0.4–2.0 V, Ic < 3 mA·Nx. BVCEO 1.6 V. |
| `npn13G2l` | c b e bn | same, plus le=2.5e-6 | Nx 1–4, le 1–2.5 µm. VBE 0.65–0.96 V, VCE 0.4–2.0 V. BVCEO 1.6 V. |
| `npn13G2v` | c b e bn | same, plus le=2.5e-6 | Nx 1–4 (model card; the PCell draws up to 8), le 1–5 µm. VBE 0.65–0.84 V, VCE 0.8–2.3 V. BVCEO 2.5 V. |
| `rsil` | 1 2 bn | w=0.5e-6 l=0.5e-6 m=1 corner=0 T=27 trise=0 | 7 Ω/□ typ. w, l ≥ 0.5 µm. |
| `rppd` | 1 2 bn | same, plus b=0 (bends) | 260 Ω/□ typ. w, l ≥ 0.5 µm. |
| `rhigh` | 1 2 bn | w=0.5e-6 l=0.96e-6, plus b=0 | 1360 Ω/□ typ. w ≥ 0.5 µm, l ≥ 0.96 µm. |
| `cap_cmim` | PLUS MINUS | w=7e-6 l=7e-6 corner=0 T=27 | 1.5 fF/µm² + 40 aF/µm of perimeter, 55 mΩ in series. w, l ≥ 1.14 µm. 7×7 µm gives 74.6 fF. |
| `sg13_lv_nmos`, `sg13_lv_pmos` | d g s b | w=3.5e-7 l=3.4e-7 (pmos 2.8e-7) ng=1 m=1 corner=0 T=27 trise=0 pre_layout=1 | PSP 103.6. w is the total width over ng fingers. 1.2 V devices; corner 0 tt, 1 ff, 2 ss. A PMOS takes negative VGS, VDS. |
| `sg13_hv_nmos`, `sg13_hv_pmos` | d g s b | same | PSP 103.6, 3.3 V devices (thick oxide). |

The PDK's other Qucs-S components (diodes, ESD devices, varicap, cap_rfcmim, taps, pnpMPA, schottky_nbl1, isolbox, nmoscl) are not kit cells: `generator/qucs_cells.json` says what each one is and why. Do not reference them with `ws://IHP_SG13G2/...`.

Layout: the kit offers IHP's own KLayout PCells (38 devices: HBTs, MOS, resistors, MIM/MOM, inductors, diodes, ESD, pads, seal ring) as circuitRF parametric cells; `kit/IHP_SG13G2/PCELLS` lists each one, compared with KLayout's drawing. They need the IHP PDK (`$PDKPATH`) and Python 3.10 or newer, and run once the kit is allowed (headless: `--trust-kit <workspace>/ihp-sg13g2-pcells`; the workspace's `ihp-sg13g2-pcells/pcell-generators.json` names the kit's `pcells/kit_entry.py`). Most parameters are text: lengths as `0.9u` or `9e-07`; a bare number in a text field is ignored and the default kept. `examples/HBT_layout` places npn13G2 at Nx 1, 4 and 8: `circuitrf render examples/HBT_layout/layout/HBT_layout.clay -o hbt.png --trust-kit examples/ihp-sg13g2-pcells`. The schematic cells have no layout view; place the PCell with the cell's values.

Notes:
- **Ranges and limits:** the HBTs are valid from −40 to 125 °C. Nothing enforces the PDK ranges, so keep the
  design inside them yourself.
- **bn:** the HBT substrate (through the PDK's Rsub ∥ Csub) or the resistor body. Tie it to ground, as the
  benches do.
- **Self-heating:** every HBT has an internal thermal node. `selft=0` turns self-heating off.
- **Reference values from the kit** (npn13G2, Nx=1):
  - Ic = 0.90 mA at VBE 0.85 V into 200 Ω from 3 V. The corners give 1.32 mA (bcs) and 0.63 mA (wcs).
  - Peak fT 354 GHz and fmax 464 GHz at VBE ≈ 0.94 V (Ic ≈ 2.8 mA per emitter), VCE 1.5 V.

## A workspace on the kit

- **Quick benches:** add a cell to `examples/`.
- **Your own workspace:**
  - Run `generator/circuitrf-ihp-workspace <dir>`. It copies the technology and writes a `.cws` with absolute
    paths.
  - For a workspace you share or commit, write the `.cws` with relative paths instead. This is for `<dir>`
    beside `kit/`:

```json
{
  "FormatVersion": 2,
  "LibraryRefs": ["../kit/IHP_SG13G2"],
  "ReferencedWorkspaces": [{"Alias": "IHP_SG13G2", "Path": "../kit/IHP_SG13G2/.cws"}],
  "KnownFiles": [],
  "DefaultTechRef": "tech/IHP_SG13G2.ctech"
}
```

  Then copy the technology in with `mkdir -p <dir>/tech && cp kit/IHP_SG13G2/tech/IHP_SG13G2.ctech <dir>/tech/`.
- **What the `.cws` fields do:**
  - `LibraryRefs` puts the kit in the Workspace tree and the palette.
  - The `IHP_SG13G2` alias is what `ws://IHP_SG13G2/<cell>` resolves through. The alias must be `IHP_SG13G2`.
  - `DefaultTechRef` is the workspace's own copy of the technology.
  - `PdkRefs` (`{"Path": "<PDK>", "Provider": "ihp-sg13g2", "TranslationVersion": 4}`) is optional. It only adds
    the PDK's own parts to the GUI palette, and their HBTs do not run in circuitRF. Use the kit's cells instead.
- **Add a cell:** use `create` with `what=cell workspace=<dir> name=<cell>`, or `circuitrf new cell <dir> <cell>`.
  Both make `<cell>/schematic/<cell>.csch`.

## Placing kit cells

### In a schematic (.csch): the supported way

- **The component:** `"Symbol": "Generic"` with `"CellRef": "ws://IHP_SG13G2/<cell>"`. List only the parameters
  you change; the rest take their defaults.
- **Pin offsets at R0** (rotation R90 maps (x, y) to (−y, x)):
  - HBTs: c (0,−300), b (−300,0), e (0,300), bn (100,0).
  - Resistors: 1 (0,−300), 2 (0,300), bn (−300,0).
  - `cap_cmim`: PLUS (0,−300), MINUS (0,300).
  - MOSFETs: d (0,−300), g (−300,0), s (0,300), b (200,0).
- **Wires:** a wire must have a point exactly on each pin it connects.
- **Other parts:** `reference components <TYPE>` gives a primitive's pins (Vdc: + (0,−200), − (0,200); Resistor:
  (0,−200), (0,200); TermG: (0,−200); Ground: (0,0); IProbe: np (0,100), nm (100,100)).

This complete bench is a common emitter with a 200 Ω load. It finds the operating point and sweeps VBE (checked:
0 errors; Ic = 0.027, 0.177, 0.901, 2.31, 3.93 mA at VBE 0.75 to 0.95 V):

```json
{
  "FormatVersion": 2,
  "CellName": "ce_amp",
  "Components": [
    { "InstanceName": "VAR1", "Symbol": "Var", "X": -1200, "Y": -900,
      "Parameters": [ { "Name": "VBE", "Expression": "0.85" }, { "Name": "VCC", "Expression": "3" } ] },
    { "InstanceName": "Q1", "Symbol": "Generic", "X": 0, "Y": 0, "CellRef": "ws://IHP_SG13G2/npn13G2",
      "Parameters": [ { "Name": "Nx", "Expression": "1" }, { "Name": "corner", "Expression": "0" } ] },
    { "InstanceName": "RL", "Symbol": "Resistor", "X": 0, "Y": -700,
      "Parameters": [ { "Name": "R", "Expression": "200" } ] },
    { "InstanceName": "VB", "Symbol": "Vdc", "X": -600, "Y": 200,
      "Parameters": [ { "Name": "Vdc", "Expression": "VBE" } ] },
    { "InstanceName": "VC", "Symbol": "Vdc", "X": 600, "Y": -700,
      "Parameters": [ { "Name": "Vdc", "Expression": "VCC" } ] },
    { "InstanceName": "G1", "Symbol": "Ground", "X": 0, "Y": 600 },
    { "InstanceName": "G2", "Symbol": "Ground", "X": 300, "Y": 100 },
    { "InstanceName": "G3", "Symbol": "Ground", "X": -600, "Y": 500 },
    { "InstanceName": "G4", "Symbol": "Ground", "X": 600, "Y": -400 },
    { "InstanceName": "M1", "Symbol": "Meas", "X": -1200, "Y": 900,
      "Parameters": [ { "Name": "Ic_mA", "Expression": "(DC1.V(\"vcc\")-DC1.V(\"nc\"))/200*1e3" } ] }
  ],
  "Wires": [
    { "Points": [ [0, -300], [0, -500] ] },
    { "Points": [ [-300, 0], [-600, 0] ] },
    { "Points": [ [0, 300], [0, 600] ] },
    { "Points": [ [100, 0], [300, 0], [300, 100] ] },
    { "Points": [ [-600, 400], [-600, 500] ] },
    { "Points": [ [0, -900], [600, -900] ] },
    { "Points": [ [600, -500], [600, -400] ] }
  ],
  "NetLabels": [
    { "X": 0, "Y": -400, "Name": "nc", "OwnerWireIndex": 0, "AlongT": 0.5 },
    { "X": -450, "Y": 0, "Name": "nb", "OwnerWireIndex": 1, "AlongT": 0.5 },
    { "X": 300, "Y": -900, "Name": "vcc", "OwnerWireIndex": 5, "AlongT": 0.5 }
  ],
  "Analyses": [
    { "Type": "dc", "Name": "DC1" },
    { "Type": "sweep", "Name": "SW1", "PsaVarName": "VBE", "PsaInnerName": "DC1",
      "PsaMode": "StepSize", "PsaStart": 0.75, "PsaStop": 0.95, "PsaStepOrCount": 0.05, "PsaKind": "Linear" }
  ]
}
```

The other cells place the same way. These two components were checked:
- `{ "InstanceName": "R1", "Symbol": "Generic", "CellRef": "ws://IHP_SG13G2/rsil", "Parameters": [ { "Name": "w", "Expression": "1u" }, { "Name": "l", "Expression": "10u" } ] }`
  gives 78.3 Ω.
- `{ "InstanceName": "C1", "Symbol": "Generic", "CellRef": "ws://IHP_SG13G2/cap_cmim" }` gives 74.6 fF.

Other rules:
- **Parameters:** a parameter takes an expression. `"corner": "crn"`, with `crn` in a Var block and a list sweep
  over 0, 1, 2, runs all three corners in one run.
- **Checking the drawing:** `netlist <file.csch>` shows what you drew. Each kit cell appears once as
  `define <cell> (pins) ... end <cell>`, and each instance as `<cell>:<name> <nets> <params>`.

### In a netlist (.cnl)

- **No direct reference:** a `.cnl` cannot name a kit cell. There is no include and no `ws://`, inside a
  workspace or with `--workspace`. `npn13G2:Q1 ...` fails with `Cell 'npn13G2' not found in libraries`.
  `netlist --to-schematic` refuses a `.cnl` that defines cells.
- **Prefer a .csch:** use one whenever a kit cell is involved.
- **If a netlist is required:**
  1. Run `netlist` on a schematic that places the cell. `examples/Kit_cells` places every kit cell.
  2. Paste its `define <cell> ... end <cell>` block into your `.cnl`.
  3. Rewrite the `File="..."` on its `VerilogA:` line, which extraction writes absolute, relative to the `.cnl`'s
     folder. For example, from `<dir>/` beside `kit/`: `File="../kit/IHP_SG13G2/models/osdi/vbic_1p3_5t.osdi"`.
  4. Instantiate it: `npn13G2:Q1 nc nb 0 0 Nx=1`. This gives the same 0.901 mA as the schematic.

## Analyses for typical tasks

Every run verb (`dc`, `sparam`, `hb`, `lp`) runs the outermost enabled sweep around its analysis. Name a chain
with `-a <name>` (MCP: `name`). `reference analyses <type>` lists every key.

| Task | Analysis | Template | Run (CLI / MCP `run`) |
|---|---|---|---|
| Operating point | `dc` | the bench above | `circuitrf dc f.csch` / `analysis=dc` |
| I–V curves, Ic vs VBE, corners | `dc` inside `sweep`s | `HBT_IcVce`, `HBT_Ic`, `Resistors` | `circuitrf dc f.csch -o r.npy` or `circuitrf hb f.csch -a SW1 -o r.npy` / `analysis=dc` (values inline; takes no `output`) or `analysis=hb name=SW1 output=r.npy` |
| S-parameters, C and Q | `sp` (`.cnl`: `type=sparam`) | `MIM_Cap` | `circuitrf sparam f.csch -o r.npy` (or `.s2p`) / `analysis=sparam` |
| fT and fmax vs bias | `sp` at one spot frequency inside sweeps | `HBT_fT_fmax` | as S-parameters |
| Large signal: Pout, gain, harmonics | `hb` inside a power sweep, `P1Tone` source | `CE_10GHz_HB` | `circuitrf hb f.csch -a SW -o r.npy` / `analysis=hb` |
| Load-pull | `lp` over a `.gam` Γ grid, `Tuner` source and load | `HBT_Loadpull` (about 20 s) | `circuitrf lp f.csch -o r.npy` / `analysis=lp`; `lpp` searches for the optima |

Notes on these analyses:
- **No DC current source and no AC analysis.** Step VBE, or bias through a resistor. Use `sp` and take
  C = −1/(ω·Im Z11), with Z11 = 50·(1+S11)/(1−S11).
- **fT and fmax** (`HBT_fT_fmax`):
  - The HBT is biased through ideal tees (1 H, 1 F) at VCE = 1.5 V. f0 = 20 GHz sits in the −20 dB/decade region.
  - The measure lines are `h21 = -2*SP1.S(2,1)/((1-SP1.S(1,1))*(1+SP1.S(2,2))+SP1.S(1,2)*SP1.S(2,1))`,
    `fT_GHz = mag(h21)*freq/1e9`, `r = SP1.S(2,1)/SP1.S(1,2)`, `U = mag(r-1)^2/(2*(K(SP1.S)*mag(r)-real(r)))` and
    `fmax_GHz = sqrt(U)*freq/1e9`.
  - Plot against Jc = Ic/Nx from `HBT_Ic`, which runs the same grid at DC.
- **Load-pull** (`HBT_Loadpull`):
  - `Tuner` uses `BiasTee=on` and `Vbias` to bias the device.
  - In a `.csch` the grid path is workspace-relative (`HBT_Loadpull/schematic/load_grid.gam`).
  - VBE 0.74 V is near class B, so gain rises with drive before it compresses.
- **harmonicaRF** (interactive harmonic load-pull):
  - Open it from the GUI, Tools ▸ harmonicaRF.
  - It drives the whole-HBT devices `models/osdi/npn13G2{,l,v}.osdi` (b, c, e; parameters Nx, le, corner, temp),
    which `build-vbic.sh` builds when `PDKPATH` is set.
  - `generator/harmonica_ihp.py charm <out.charm> --device npn13G2 --nx 4 --vbe 0.8 --vce 1.6 --f 50e9` writes a
    document.
- **Reading results:** `read` a result with `only`, `at` (`VBE=0.9`, `freq=2GHz`) and `range`, or with
  `result=summary` for the shape only. On the CLI, add `--json` to get the values.

## EM on the SG13G2 stackup

**The technology:** the workspace's copy of `IHP_SG13G2.ctech`.
- It has all 378 KLayout layers with their GDS numbers.
- It has no DRC rules, so `check` notes that on every layout. Use KLayout's IHP decks for DRC.
- Layouts (`.clay`) name layers by GDS number. A port is a `Label` with `"IsPort": true`.
- IHP's PCells are drawn through KLayout. See `examples/inductor/inductor_from_pcell.py`
  (`klayout -b -r <script>`).

The stackup, top to bottom (oxide εr 4.1, with the oxide between levels not listed). It is open at the top and
grounded at the backside:

| Level | GDS | Thickness | Notes |
|---|---|---|---|
| Passivation | – | 0.4 µm SiN (εr 6.6) on 1.5 µm SiO2 | |
| TopMetal2 | 134/0 | 3.0 µm | 30.3 MS/m; TopVia2 133/0 to TopMetal1 |
| TopMetal1 | 126/0 | 2.0 µm | 27.8 MS/m; TopVia1 125/0 to Metal5 |
| MIM | 36/0 | 0.15 µm on a 40 nm film (εr 6.78) | Vmim 129/0 to TopMetal1 |
| Metal5…Metal2 | 67, 50, 30, 10 /0 | 0.49 µm each, 0.54 µm apart | 23.2 MS/m; Via4…Via1 66, 49, 29, 19 /0 |
| Metal1 | 8/0 | 0.42 µm | 21.7 MS/m; Cont 6/0 to Activ (1/0) |
| EPI, substrate | – | 3.75 µm at 20 Ω·cm, 750 µm at 50 Ω·cm | the backside is the ground |

| Solver | Use for | Ports | Cost (the example inductor, 16 cores) |
|---|---|---|---|
| Palace (3D FEM): `"Solver3D": "Palace"` | the reference | `Ports3D`: each lumped port returns to a drawn conductor (`"Return": "Metal1"`, a Metal1 ring under the terminals) | 1 h 18 min, 222k unknowns (second order, `Quality: Draft`) |
| EMerge (3D FEM): `"Solver3D": "Emerge"` | quick looks | as Palace | 28 s. At circuitRF's default mesh it reads L about 25 % low and resonates early; refine the mesh before trusting it |
| openEMS (FDTD): `"Solver3D": "OpenEms"` | not for µm features at GHz | as Palace | about 9 h estimated |
| circuitRF planar MoM (no `Solver3D`) | planar structures | an internal delta-gap port on chip, see below | about 2 h, 13,211 unknowns, 6.4 GB per point |

**Why the planar MoM needs a delta-gap port on chip.** The planar kernel returns every port to the stackup's
ground, which here is the backside, 750 µm down. It de-embeds an edge port with calibration lines whose feeds
must be clear of other metal by several substrate heights. On chip that is impossible, and on the inductor the
lines would also need 84–167 GB, so circuitRF refuses the run. An internal delta-gap port is a cut with metal on
both sides. It needs no calibration and is reported at the gap. How to use it:
- Join the two terminals with a bar.
- Put one port label on the bar with `"PortKind": "InternalDeltaGap"`, and a `PortDirection` across the cut.
  The run then measures the differential impedance.
- See `examples/inductor/layout/inductor_mom.clay` and `examples/inductor/em/inductor_mom.cem`.

Running EM:
- **Check the cost first:** `check` the `.cem` (it reports the mesh budget), then
  `circuitrf em <cem> --dry-run` (MCP: `run analysis=em dryRun=true`) for unknowns, memory and time.
- **Long runs** go in the background. Over MCP use `async=true`, then `job action=status|result`.
- **Results** go to `<workspace>/results/`, for example `inductor.palace.s2p` or `inductor_mom.s1p`, each with
  a `.cemr` and an `_em.npy`.
- **Using the results in a circuit:** place them with an `SnP` component (`examples/inductor_TB`).
  - Differential L and Q of a two-port: Zdiff = Z11 + Z22 − Z12 − Z21, L = Im Zdiff/ω, Q = Im Zdiff/Re Zdiff.
  - The inductor gives about 440 pH (Palace) to 580 pH (MoM) at 10 GHz. The 3D layout's Metal1 ring acts as a
    shorted turn.

## circuitRF's MCP tools

circuitRF 1.7.3's server offers 21 tools: `find`, `reference`, `create`, `check`, `explain`, `netlist`, `run`,
`read`, `render`, `plot`, `job`, `batch`, `history`, `solver`, `convert`, `import`, `lvs`, `recognize`,
`impedance`, `review` and `model`. No tool writes your text: write documents with your own file tools.

The flow:
1. `find` what is there.
2. Use `reference` for the format: topics `schematic`, `netlist`, `analyses`, `measurements`,
   `components` + `type`; `component-index` first.
3. Write the file.
4. `check` it (0 errors, and read the warnings).
5. `netlist` it.
6. `run` it.
7. `read` the results.
8. `render` or `plot` to look at it.

These calls were checked, with paths relative to a root that holds `my_ws/`:

```json
{"tool": "create",  "arguments": {"what": "cell", "workspace": "my_ws", "name": "ce_amp"}}
{"tool": "check",   "arguments": {"path": "my_ws/ce_amp"}}
{"tool": "netlist", "arguments": {"path": "my_ws/ce_amp/schematic/ce_amp.csch"}}
{"tool": "run",     "arguments": {"analysis": "dc", "path": "my_ws/ce_amp/schematic/ce_amp.csch", "only": ["Ic_mA"]}}
{"tool": "run",     "arguments": {"analysis": "hb", "name": "SW1", "path": "my_ws/ce_amp/schematic/ce_amp.csch", "output": "my_ws/results/ce_amp.npy", "result": "summary"}}
{"tool": "read",    "arguments": {"path": "my_ws/results/ce_amp.npy", "only": ["Ic_mA"], "at": ["VBE=0.9"]}}
{"tool": "render",  "arguments": {"path": "my_ws/ce_amp/schematic/ce_amp.csch", "output": "my_ws/ce_amp.png", "attachImage": true}}
{"tool": "reference", "arguments": {"topic": "components", "type": "Vdc"}}
```

Server behaviour to expect:
- **Outside the root:** a document may reference the kit outside the root, but an output path outside it is
  refused. The server creates `<root>/.circuitrf-scratch/` when it names that folder in a refusal.
- **Missing tools:** if the tools are not there, start a new session. Clients load MCP servers at session start.

## Known notes

- **The thermal note on HBT runs:** every HBT run notes that "the thermal node ... reaches its reference only
  through 1.14E+04 °C/W, which is not a thermal resistance". This is expected: the value is the PDK's own rth for
  a small SiGe HBT. Ignore it.
- **Expected warnings:** `check examples` gives 0 errors and 4 warnings. Two schematics declare no analysis, and
  two layouts have no DRC rules in the technology.
- **The missing VBIC model:** this is the error shown above. Run `generator/build-vbic.sh`.
- **EMerge:** at circuitRF's default mesh it under-reads on-chip inductance.
- **Results:** `results/*` is git-ignored except the data displays (`*.cdd`). `inductor_TB` needs the EM runs
  first.

## Example benches

| Bench | Shows |
|---|---|
| `Kit_cells` | every cell with its default parameters (no analysis) |
| `HBT_IcVce` | npn13G2 output curves, VCE 0–1.5 V, VBE 0.80–0.90 V |
| `HBT_Ic` | Ic and Jc = Ic/Nx over Nx 1, 2, 4, 8, 10 and VBE |
| `HBT_fT_fmax` | fT and fmax against VBE and Jc |
| `Resistors` | rsil, rppd and rhigh at the wcs corner, V/I to 10 V |
| `MIM_Cap` | cap_cmim 70×70 µm, C and Q from 100 kHz to 300 GHz |
| `CE_10GHz_HB` | common emitter at 10 GHz: Pout, Gt, H2, H3 against drive |
| `HBT_Loadpull` | npn13G2 Nx=8 at 50 GHz, Pout and PAE contours at 1 dB compression |
| `inductor` | a two-turn TopMetal2 coil from IHP's `inductor2` PCell, one EM setup per solver |
| `inductor_TB` | differential L and Q from every EM run |
