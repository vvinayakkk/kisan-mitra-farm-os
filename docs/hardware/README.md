# Hardware source and station boundary

`hardware/hls/` contains C++ sensor-fusion and rain-prediction accelerator source, testbenches and Vitis HLS scripts. `hardware/rtl/` and `hardware/ip_repo/` contain RTL and integration source. These files describe the accelerator implementation; synthesis scripts and testbenches are not evidence that a physical board is attached to the running application.

The web station scene is a React Three Fiber visualization. Canonical server enrollment associates a device credential with an owned station. Ingestion checks units, timestamps, station identity and replay sequence before storing a packet receipt. A current-looking animation does not count as a received measurement. Where a provider forecast or model output appears beside station data, the UI must retain its origin and time basis.

For source-level accelerator verification, use the scripts in `hardware/hls/` with a compatible Vitis HLS installation and target board files. The [hardware directory README](../../hardware/hls/README.md) lists the available commands. Device commissioning, calibration and command acknowledgments require physical hardware and are separate from a local API test.
