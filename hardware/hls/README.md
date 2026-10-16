# HLS accelerator sources

This directory contains C++ source, headers, testbenches and Vitis HLS scripts for sensor fusion and rain prediction. `sensor_fusion.cpp` and `sensor_fusion.h` define the fusion accelerator; `sensor_fusion_tb.cpp` exercises it. `rain_predictor/` contains the rain-prediction source and testbench. The scripts in this directory support C-level verification and synthesis with a compatible Vitis HLS installation and target board files.

```bash
vitis_hls -f run_csim.tcl
vitis_hls -f run_synth.tcl
```

The presence of source or a successful software test does not establish that a board is connected to the running API. Synthesis timing, resource use and packet integration depend on the selected toolchain and target. Record measured reports with their tool version and clock constraint before making a performance claim. Device enrollment and telemetry validation are documented in the [hardware integration guide](../../docs/hardware/README.md).
