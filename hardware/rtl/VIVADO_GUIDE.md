# Vivado RTL integration

This guide covers the source in [`hardware/rtl/`](./). It is a board integration procedure, not a claim that a bitstream or physical station has been commissioned. Use a Vivado release and board definition compatible with the target device; record both versions with synthesis and timing reports.

## Source and verification

Create an RTL project in a local build directory outside Git. Add `sensor_fusion_pkg.vh`, `sensor_fusion.v` and `sensor_fusion_axi.v` as design sources. Add `sensor_fusion_tb.v` as a testbench and run behavioral verification before packaging. The wrapper's 8-bit AXI4-Lite address bus and register decoding are defined in `sensor_fusion_axi.v`; the register offsets and Q8.8 constants are defined in `sensor_fusion_pkg.vh`.

If the target is the ZC706, choose the installed ZC706 board definition and Zynq-7000 processing-system preset. Enable a PS-to-PL AXI master and an appropriate PL clock/reset. Package the wrapper as a custom IP, add it to a block design, connect its AXI4-Lite slave and clock/reset signals, and validate the design. The optional interrupt must be connected and enabled explicitly if the host software uses it. Assign the base address in Vivado's Address Editor; do not assume a fixed board address.

| Offset | Register | Access | Value |
| --- | --- | --- | --- |
| `0x00` | Control | Read/write | Start and reset writes; busy readback. |
| `0x04` | Status | Read | Accelerator status and alert level. |
| `0x08` | Soil input | Read/write | Q8.8 sensor value. |
| `0x0C` | Temperature input | Read/write | Q8.8 sensor value. |
| `0x10` | Humidity input | Read/write | Q8.8 sensor value. |
| `0x14` | Light input | Read/write | Q8.8 sensor value. |
| `0x18` | Fusion output | Read | Q8.8 result. |
| `0x1C` | Stress output | Read | Q8.8 result. |
| `0x20` | Timestamp | Read | Last processing timestamp. |
| `0x24` | Version | Read | RTL version constant. |

## Build and commissioning boundary

After behavioral verification, run synthesis and implementation with the selected clock and pin constraints. Review utilization, setup/hold timing, address map and CDC warnings before generating a bitstream. Export the hardware description and bitstream to a private build-artifact location, not this source tree. Record the assigned base address in the device-specific host configuration.

Host access must use the assigned address, correct 32-bit register width, timeout-bounded completion polling and access restricted to the device operator. A mapped register read alone does not prove a sensor packet reached Kisan Mitra. Enroll the device with a server-verified station credential and verify packet units, sequence, timestamp, calibration and receipt through the API. See the [hardware boundary](../../docs/hardware/README.md) for the data path. No bitstream or measured board report is checked in.
