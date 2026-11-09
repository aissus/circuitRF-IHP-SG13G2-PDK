# IHP SG13G2 Kit for circuitRF

A device kit for [circuitRF](https://github.com/potatobeanradio/circuitRF) on the
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK) open 130 nm SiGe BiCMOS process, with an example
workspace. Built and validated from the PDK by
[circuitRF-IHP-SG13G2-PDK](https://github.com/aissus/circuitRF-IHP-SG13G2-PDK); `kit/IHP_SG13G2/BUILD` names
the PDK commit, the circuitRF version and the validation result.

> [!IMPORTANT]
> Requires **circuitRF 1.7.5 or newer**. The HBT cells also need their VBIC model compiled once (step 2),
> which takes **OpenVAF**. The [IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) container has
> OpenVAF and the PDK.

## Contents

```text
kit/IHP_SG13G2/       the kit: cells, technology (tech/IHP_SG13G2.ctech), compiled R3 and PSP 103 models
examples/             an example workspace on the kit (open examples/.cws)
generator/            the generator; build-vbic.sh compiles the VBIC models
.claude/, CLAUDE.md   instructions and a skill for AI coding agents
.mcp.json             circuitRF's MCP server, for agents that use it
LICENSE, NOTICE       Apache-2.0, as the IHP PDK
```

| Cell | Device | Parameters |
|---|---|---|
| `npn13G2`, `npn13G2l`, `npn13G2v` | SiGe HBTs | Nx, (le), corner, T, dtemp, selft |
| `rsil`, `rppd`, `rhigh` | poly resistors | w, l, (b), m, corner, T, trise |
| `cap_cmim` | MIM capacitor | w, l, corner, T |
| `sg13_lv_nmos`, `sg13_lv_pmos` | 1.2 V MOSFETs | w, l, ng, m, corner, T, trise, pre_layout |
| `sg13_hv_nmos`, `sg13_hv_pmos` | 3.3 V MOSFETs | w, l, ng, m, corner, T, trise, pre_layout |

The corner parameter is 0 for typ, 1 for bcs and 2 for wcs (MOSFETs: tt, ff, ss).

## Getting started

1. Unpack the archive anywhere. The kit is relocatable: its cells name their models relative to
   `kit/IHP_SG13G2/.cws`.
2. Compile the VBIC models, once:

   ```bash
   generator/build-vbic.sh          # needs openvaf on PATH (or OPENVAF=/path/to/openvaf)
   ```

   It writes `kit/IHP_SG13G2/models/osdi/vbic_1p3_5t.osdi` from VBIC 1.3's public Verilog-A source. With
   the IHP PDK at `$PDKPATH`, as in IIC-OSIC-TOOLS, it also builds the harmonicaRF devices.
3. Open `examples/.cws` in circuitRF, or start a workspace of your own:

   ```bash
   generator/circuitrf-ihp-workspace my_project
   ```

The resistors, the MIM capacitor, the MOSFETs and the technology work without step 2.

IHP's KLayout PCells (38 devices; `kit/IHP_SG13G2/PCELLS`) come with circuitRF's import of the IHP PDK,
which `examples/` records at `/foss/pdks/ihp-sg13g2`, the IIC-OSIC-TOOLS location (with the PDK elsewhere:
`circuitrf import pdk <PDK> --into examples`). They need Python 3.10 or newer, and circuitRF asks once before
it runs them (headless: `--trust-kit examples/ihp-sg13g2-pcells`).

A workspace of your own from `generator/circuitrf-ihp-workspace` imports the PDK too: the PDK's own parts
(`pdk://ihp-sg13g2/<part>`) simulate there, its HBTs on the kit's VBIC 1.3 (step 2), which the script
declares to stand in for ngspice's built-in VBIC.

## License

Apache-2.0, as the IHP Open PDK; see LICENSE and NOTICE. The VBIC models are not distributed: step 2
compiles them from their source.
