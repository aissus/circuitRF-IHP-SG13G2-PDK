# Example workspace

Test benches on the IHP SG13G2 kit. This folder is one circuitRF workspace; its benches place the cells
of `../kit/IHP_SG13G2`.

- **From a release:** run `generator/build-vbic.sh` once, for the HBTs' VBIC model.
- **From the repository:** build the kit with `./kit.sh generator/build.sh`. The build also writes this
  workspace's copy of the technology (`tech/`) and its harmonicaRF documents (`harmonica/`).

Open `examples/.cws` with File ▸ Open Workspace in circuitRF 1.7.3 or newer, or with
`./kit.sh circuitrf examples/.cws` in the repository.

| Bench | What it shows | Ported from |
|---|---|---|
| `HBT_IcVce` | npn13G2 (Nx=1) output curves: Ic against VCE from 0 to 1.5 V, VBE 0.80 to 0.90 V | Qucs-S `dc_hbt_13g2` |
| `Resistors` | rsil, rppd and rhigh (10 µm wide) at the wcs corner: V/I from 0 to 10 V | Qucs-S `resistors` |
| `MIM_Cap` | cap_cmim 70 × 70 µm: C and Q from 100 kHz to 300 GHz | Qucs-S `ac_mim_cap` |
| `HBT_fT_fmax` | npn13G2 fT and fmax against VBE at VCE = 1.5 V, for Nx = 1, 2, 4, 8, 10 | |
| `HBT_Ic` | the same bias network and Nx × VBE grid at DC: Ic, and Jc = Ic/Nx, the x-axis of the Jc plot | |
| `HBT_Loadpull` | npn13G2 (Nx=8) load-pull at 50 GHz: Pout and PAE contours at 1 dB compression | |
| `CE_10GHz_HB` | npn13G2 common emitter at 10 GHz: an HB drive sweep, with Pout, Gt, H2 and H3 measured | |
| `inductor` | a two-turn TopMetal2 inductor from IHP's PCell: its layout, its 3D view, and one EM setup per solver | IHP's `inductor2` PCell |
| `inductor_TB` | the inductor's series L and Q from every EM run, side by side | |
| `Kit_cells` | every kit cell placed once with its default parameters: the overview picture in the top-level README | |
| `harmonica/` | harmonicaRF documents: npn13G2 and npn13G2v at Nx = 1, 2, 4, 8, at 50 GHz (written by the build) | |

## Running them

From the repository's top folder:

```bash
./kit.sh bash -c 'cd examples &&
  circuitrf hb HBT_IcVce/schematic/HBT_IcVce.csch -a SW2 -o results/HBT_IcVce.npy &&
  circuitrf hb Resistors/schematic/Resistors.csch -a SW1 -o results/Resistors.npy &&
  circuitrf sparam MIM_Cap/schematic/MIM_Cap.csch -o results/MIM_Cap.npy &&
  circuitrf hb HBT_Ic/schematic/HBT_Ic.csch -a SW0 -o results/HBT_Ic.npy &&
  circuitrf hb HBT_fT_fmax/schematic/HBT_fT_fmax.csch -a SW0 -o results/HBT_fT_fmax.npy &&
  circuitrf hb CE_10GHz_HB/schematic/CE_10GHz_HB.csch -a SW -o results/CE_10GHz_HB.npy &&
  circuitrf lp HBT_Loadpull/schematic/HBT_Loadpull.csch -o results/HBT_Loadpull.npy'
```

The longest run, the load-pull, takes about 20 s. Each verb runs the whole parametric sweep that
wraps its analysis, and `-a <sweep>` names the sweep. In the GUI, press Simulate on a bench as usual.

Each bench's data display (`results/<bench>.cdd`) reads the `.npy` its run writes. Every plot autoscales,
and a marker reads the curves where it matters:

| Display | Marker m1 |
|---|---|
| `HBT_IcVce` | Ic at VCE = 1 V |
| `Resistors` | each resistor's V/I at 5 V |
| `MIM_Cap` | C and Q at 1 GHz |
| `HBT_fT_fmax` | every Nx at VBE = 0.94 V (the peak), and m2 at the peak Jc |
| `inductor_TB` | L and Q of every solver at 10 GHz |

The inductor's EMerge L trace is left out of the autoscale: it goes through resonance near 40 GHz and
would set the scale. The pictures below are these displays, from `docs/make-figures.sh`, on white.

Against the same benches run on circuitRF 1.6.0 with the kit's previous build:
- **Six benches are identical** in every number: everything except the load-pull.
- **The load-pull** converges at 5 more of its 1,568 drive points (the lowest drives at two loads) and
  agrees within 0.09 dB in Pout and Gt where both converged. That change is circuitRF's load-pull
  engine between those versions, not the kit.

## Libraries

The workspace references two libraries:

- **IHP_SG13G2**, the kit, at `../kit/IHP_SG13G2`. The `.cws` names it twice:
  - as a library, so it appears in the Workspace tree and the palette;
  - under the alias `IHP_SG13G2`, which is how the benches place its cells (`ws://IHP_SG13G2/npn13G2`).
  Moving the kit means changing those two paths.
- **ihp-sg13g2**, the PDK itself, imported by circuitRF from `/foss/pdks/ihp-sg13g2` (where the image
  has it; a `.cws` cannot take a variable there).
  - It appears in File ▸ Manage Libraries and in the palette: 216 parts from IHP's xschem symbols and
    ngspice models, the corner libraries, and IHP's KLayout PCells.
  - circuitRF translates these parts itself, and they are not checked against ngspice the way the kit's
    cells are.
  - Its HBTs are ngspice's VBIC, which circuitRF does not run: use the kit's cells.

## fT and fmax

`HBT_fT_fmax` biases npn13G2 through ideal bias tees (1 H, 1 F) at VCE = 1.5 V. It steps Nx over 1, 2, 4,
8 and 10 (sweep SW0), and inside that VBE from 0.80 to 0.98 V (SW1). At each point it runs an S-parameter
analysis at one spot frequency, f0 = 20 GHz (a VAR, so it can be changed). The spot frequency sits in the
−20 dB/decade region of h21 and U, so:

    fT   = |h21|·f0,     h21 = -2·S21 / ((1-S11)(1+S22) + S12·S21)
    fmax = sqrt(U)·f0,   U = |S21/S12 - 1|² / (2·(K·|S21/S12| - Re(S21/S12)))   (Mason)

| Nx | 1 | 2 | 4 | 8 | 10 |
|---|---|---|---|---|---|
| peak fT (GHz) | 354 | 356 | 355 | 355 | 355 |
| peak fmax (GHz) | 464 | 461 | 458 | 455 | 455 |

The peaks sit at VBE = 0.93 to 0.945 V; for Nx = 1 that is Ic ≈ 2.8 mA. IHP publishes 350 GHz fT and
450 GHz fmax for SG13G2. The PDK model run directly in ngspice (Nx = 1, VBE = 0.94 V) gives fT = 356 GHz
at Ic = 2.788 mA, against the kit's 354 GHz at 2.786 mA.

The display has two plots, with fT solid and fmax dashed, one colour per Nx:
- **Against VBE**, read directly from `HBT_fT_fmax`.
- **Against Jc = Ic/Nx on a log axis**, the usual way to compare sizes: the five curves fall on top of each
  other, peaking at Jc ≈ 2.8 mA per emitter. An S-parameter run carries no DC currents, so `HBT_Ic` runs
  the same grid at DC, and each trace takes its x values from `Jc_mA` in `results/HBT_Ic.npy`. Run both
  benches after a change.

Markers m1 and m2 read every trace at the same x. Drag one and all ten values in its box follow.

![fT and fmax](../docs/images/white/HBT_fT_fmax.png)

## The other benches

![HBT output curves](../docs/images/white/HBT_IcVce.png)
![Resistors](../docs/images/white/Resistors.png)
![MIM capacitor](../docs/images/white/MIM_Cap.png)
![Load-pull](../docs/images/white/HBT_Loadpull.png)

In `HBT_Loadpull`, VBE = 0.74 V biases the HBT close to class B, so its gain rises with drive before it
compresses. At 50 Ω, Gt goes from −8 dB at −20 dBm to +6 dB at −2 dBm. Keep that in mind when reading the
1 dB compression contours, or raise VBE for a class-A bench.

### harmonicaRF

Open a document with `./kit.sh circuitrf examples/harmonica/npn13G2_Nx4_50GHz.charm`, or Tools ▸
harmonicaRF ▸ File ▸ Open.
- **The device** is the kit's `models/osdi/npn13G2.osdi`: VBIC 1.3 compiled with IHP's scaling inside, so
  its row shows only Nx, corner (0 typ, 1 bcs, 2 wcs) and temp. Change Nx and the device rescales.
- **The bias** starts at VBE 0.74 V and VCE 1.6 V, with the Nx = 8 match scaled by 8/Nx.
- **Why the build writes them:** a `.charm` names its compiled device by absolute path. circuitRF uses
  that path as the device's identity, so the documents are made for wherever the kit was built.

Make others with `./kit.sh generator/harmonica_ihp.py charm <out.charm> --device npn13G2l --nx 6 --vbe 0.8
--vce 2.0 --f 94e9`.

## Differences from the Qucs-S originals

- `HBT_IcVce` steps VBE where Qucs-S steps IB: circuitRF has no DC current source.
- `MIM_Cap` uses an S-parameter sweep where Qucs-S uses AC: circuitRF has no AC analysis.
  C = −1/(ω·Im Z11).
- Parts the kit does not have are left out: the ptap/ntap body ties (the resistor bodies go to ground
  instead), and cap_rfcmim.

## The inductor

`inductor/inductor_from_pcell.py` draws the inductor with IHP's own `inductor2` PCell:
- two turns of 5.4 µm TopMetal2 at 4.1 µm spacing;
- the smallest centre opening the PCell allows for them (62.63 µm, so 92.5 µm across);
- both terminals on TopMetal1.

It writes two layouts:

```bash
./kit.sh klayout -b -r examples/inductor/inductor_from_pcell.py
```

| Layout | For | Ports |
|---|---|---|
| `inductor.clay` | the 3D solvers (Palace, EMerge, openEMS) | one lumped port on each terminal, down to a 20 µm Metal1 ring 22 µm clear of the coil |
| `inductor_mom.clay` | circuitRF's planar MoM | a TopMetal1 bar joins the two terminals, and one internal delta-gap port cuts it in the middle |

![The inductor, for the 3D solvers](../docs/images/white/inductor.png)

**Why the planar MoM gets its own layout.** The planar kernel returns every port to the
technology's ground, which here is the backside, 750 µm below. It also de-embeds an edge port by
solving calibration lines beside the structure. For this coil those lines would need 167 GB, and
their feeds must be clear of other metal by several substrate heights, which two terminals 9.5 µm
apart can never be. (circuitRF says both, and refuses the run.) A delta-gap port needs neither: it is a
cut with metal on both sides. So the MoM measures the coil differentially, terminal to terminal, and
the bar adds a few pH of its own.

![The inductor, for the planar MoM](../docs/images/white/inductor_mom.png)

`inductor_TB` compares the runs on that same footing. Each 3D run's 2-port gives its differential
impedance, and the MoM's 1-port is that impedance directly:

    Zdiff = Z11 + Z22 - Z12 - Z21 = 2·Z0·(1 - S11·S22 + S12·S21 - S12 - S21) / ((1 - S11)(1 - S22) - S12·S21)
    L = Im(Zdiff) / ω,   Q = Im(Zdiff) / Re(Zdiff)

Run the EM setups first, then the bench:

```bash
./kit.sh circuitrf em examples/inductor/em/inductor_palace.cem    # also _emerge, _mom
./kit.sh bash -c 'cd examples && circuitrf sparam inductor_TB/schematic/inductor_TB.csch -o results/inductor_TB.npy'
```

Differential L and Q on circuitRF 1.7.3, each solver at the setup's own settings (16 cores, on a
shared machine):

| Run | 2 GHz | 10 GHz | 20 GHz | 30 GHz | 40 GHz | Time |
|---|---|---|---|---|---|---|
| Palace (second-order elements, no refinement) | 448 pH, Q 1.9 | 436 pH, Q 7.4 | 467 pH, Q 11.5 | 538 pH, Q 12.7 | 691 pH, Q 11.3 | 1 h 18 min, 222,122 unknowns |
| circuitRF planar MoM | 583 pH, Q 2.1 | 583 pH, Q 8.7 | 601 pH, Q 13.0 | 646 pH, Q 15.6 | 727 pH, Q 16.1 | 2 h, 13,211 unknowns |
| EMerge (circuitRF's default mesh) | 337 pH, Q 1.5 | 338 pH, Q 5.4 | 411 pH, Q 7.1 | 679 pH, Q 5.3 | past resonance | 28 s, 5,616 tetrahedra |

![Differential L and Q](../docs/images/white/inductor_TB.png)

How to read it:
- **The MoM and the 3D runs do not solve quite the same structure.** The 3D layout has the Metal1 ring,
  a closed loop 22 µm around the coil, which acts as a shorted turn. Cutting it with a 5 µm slit
  raises EMerge's L by 13 % at 2 GHz and 16 % at 10 GHz. The MoM layout has no ring: at the 1.35 µm
  grid the coil's 5.4 µm lines need, meshing the ring is far past what one machine holds.
- **Palace without the ring's effect** would read about 505–510 pH. The modified Wheeler formula
  (Mohan et al., 1999) gives 521 pH for the coil alone, without its leads. The MoM reads about 15 %
  above that corrected Palace value. Its sheet conductors (no metal thickness) and the bar can account
  for part of it; this comparison does not separate them.
- **Q** rises the same way on both up to 20 GHz. The MoM's is higher, partly because there is no ring to
  lose energy to.
- **EMerge** at circuitRF's default mesh reads L about 25 % low and resonates early. It needs a finer
  mesh for features this small in a thick substrate.

`inductor_openems.cem` is the same model for openEMS. On this coil its grid has 1.8 million cells, and the
0.2 µm cell its finest feature needs sets 1.8 million time steps per port, which circuitRF estimates at about
9 hours. FDTD on micrometre features at GHz is the expensive case. It is not in the comparison.
