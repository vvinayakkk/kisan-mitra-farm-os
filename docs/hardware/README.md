# Hardware source and station boundary

`hardware/hls/` contains C++ sensor-fusion and rain-prediction accelerator source, testbenches and Vitis HLS scripts. `hardware/rtl/` and `hardware/ip_repo/` contain RTL and integration source. These files describe the accelerator implementation; synthesis scripts and testbenches are not evidence that a physical board is attached to the running application.

The web station scene is a React Three Fiber visualization. Canonical server enrollment associates a device credential with an owned station. Ingestion checks units, timestamps, station identity and replay sequence before storing a packet receipt. A current-looking animation does not count as a received measurement. Where a provider forecast or model output appears beside station data, the UI must retain its origin and time basis.

For source-level accelerator verification, use the scripts in `hardware/hls/` with a compatible Vitis HLS installation and target board files. The [hardware directory README](../../hardware/hls/README.md) lists the available commands. Device commissioning, calibration and command acknowledgments require physical hardware and are separate from a local API test.

## Connect a station

Create a farm and plot, then enroll a physical station through `POST /api/stations/enroll`. Keep the returned device key on the device; the server stores only its hash. Send `POST /api/sensors/ingest` with `Authorization: Device <device key>` and this JSON shape:

```json
{
  "station_id": "enrolled station UUID",
  "boot_id": "new UUID for each device boot",
  "sequence": 1,
  "observed_at": "current ISO-8601 device time with timezone",
  "measurements": {
    "temperature_c": 27.5,
    "humidity_pct": 61,
    "soil_moisture_pct": 35
  }
}
```

Use the device clock for `observed_at`; keep `boot_id` stable during one boot and increment `sequence` for every new packet. Retrying an identical packet is safe. A changed packet with the same boot and sequence is rejected. The device must send calibrated values in the stated units. Successful receipt updates the station's `last_received_at`; it does not command irrigation.

## Connect the fusion accelerator

The fusion RTL exposes a 32-bit AXI4-Lite register window. On the Linux host that owns the FPGA memory map, configure `ENABLE_FPGA=True`, `FPGA_MMIO_PATH=/dev/mem`, and `FPGA_FUSION_BASE` to the physical base address assigned in Vivado's Address Editor. A UIO mapping can use its `/dev/uioN` path and a base of `0x0`. The process needs permission to open that mapping. `FPGA_TIMEOUT_MS` bounds each calculation. Do not enable this on a remote API host that cannot access the board's registers.

`GET /api/fpga/status` reads the IP version register and reports whether the configured register window responds with the expected version. `POST /api/fpga/fusion` writes Q8.8 inputs, starts one calculation, waits for a new completion timestamp, and returns the unmodified hardware registers. Missing mappings, version mismatches, and timeouts return unavailable rather than a hardware result. The register map and build procedure are in the [Vivado guide](../../hardware/rtl/VIVADO_GUIDE.md).

The rain-prediction RTL has a separate address map and is not exposed by the register bridge. The rain API does not claim a physical result when the fusion accelerator alone is connected. A version probe establishes access to the mapped IP, while board timing, sensor wiring, calibration, and packet delivery still need an on-device commissioning run.
