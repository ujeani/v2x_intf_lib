# v2x_intf_lib

IT Telecom V2X OBU/RSU interface library.

## Overview

This repository provides a Python UDP-based V2X interface and example programs for receiving and handling J2735-based message payloads.

## Repository Structure

- `src/v2xintf.py`: Core V2X interface implementation (`V2XInterface`).
- `src/gps_intf.py`: GPS position interface implementation (`GpsPositionInterface`, `GpsPosition`).
- `src/v2xintf_ex.py`: Basic example app (console mode, with optional PyQt6 demo UI).
- `src/v2xintf_ex_bsm.py`: BSM-focused example using ASN.1 tooling.
- `src/v2xintf_ex_msg_gps.py`: Example running `V2XInterface` (BSM parsing) and `GpsPositionInterface` together.
- `src/J2735SET_202409/`: ASN.1 module collection.

## Prerequisites

- Python 3.9 or newer
- pip

## Installation

Install required packages:

```bash
pip install -r requirements.txt
```

Current required dependency:

- `asn1tools`

Optional dependency for GUI demo in `src/v2xintf_ex.py`:

```bash
pip install PyQt6
```

## Prepare V2X Device

1. Set up the OBU or RSU and connect it to the network.
2. Set the OBU/RSU IP address (see the device's "Changing IP address" instructions).
3. Modify `forwardip` and `forwardport` in `forward.cfg`.
   - The Python application that receives the message from the OBU or RSU must be running on the computer whose IP address is `forwardip` at port `forwardport`.
   - `forwardip`/`forwardport` is the direction the OBU/RSU forwards messages *to* this app, so `forwardport` must match the app's `--local-port` (default `5398`, see [Usage](#usage)) — or `--gps-port` (default `5999`) if the device forwards GPS packets. This is separate from `--remote-address`/`--remote-port` (default `127.0.0.1:1516`), which is the opposite direction: where this app sends messages *to* the device via `sendV2XMessage`.

## Using the Library in Your Application

Both `V2XInterface` and `GpsPositionInterface` run their UDP receiver on a background
thread and deliver parsed data to a callback you provide. They are independent of
each other and can be started/stopped separately, on their own local ports.

### V2XInterface (DSRC/J2735 messages)

```python
from v2xintf import V2XInterface

def on_v2x_message(data: bytes, msg_id: int):
    if msg_id is None:
        print(f"Unknown/non-SAE message: {len(data)} bytes")
        return
    print(f"Received message ID {msg_id}: {len(data)} bytes")
    # e.g. decode `data` with your J2735 ASN.1 spec based on msg_id

v2x = V2XInterface(
    callback=on_v2x_message,
    remote_address="127.0.0.1",
    remote_port=1516,
    local_port=5398,
)
v2x.start()

# Send an outgoing message (raw DSRC payload bytes + message type name from WAVE_MSG_IDS)
v2x.sendV2XMessage(b"\x00\x14...", "BSM")

# ... later
v2x.stop()
```

### GpsPositionInterface (fixed-format GPS UDP messages)

```python
from gps_intf import GpsPositionInterface, GpsPosition

def on_gps_message(data: bytes, position: GpsPosition | None):
    if position is None:
        return  # packet did not match the expected 20-byte fixed format
    print(f"lat={position.latitude_deg:.7f}, lon={position.longitude_deg:.7f}, "
          f"speed={position.speed_mps:.2f} m/s, heading={position.direction_deg:.2f} deg")

gps = GpsPositionInterface(callback=on_gps_message, local_port=5999)
gps.start()

# ... later
gps.stop()
```

`GpsPosition` exposes both the raw J2735-scaled integer fields (`latitude_raw`,
`longitude_raw`, `speed_raw`, `direction_raw`, `timestamp_ms`) and convenience
properties in human-readable units (`latitude_deg`, `longitude_deg`, `speed_mps`,
`direction_deg`).

See `src/v2xintf_ex_msg_gps.py` for a complete example that runs both interfaces
together, including a J2735 ASN.1 decode of received BSMs.

## Usage

Run the general interface example:

```bash
python src/v2xintf_ex.py --remote-address 127.0.0.1 --remote-port 1516 --local-port 5398
```

Run the BSM example:

```bash
python src/v2xintf_ex_bsm.py --remote-address 127.0.0.1 --remote-port 1516 --local-port 5398
```

Run the Custom message and GPS example:

```bash
python src/v2xintf_ex_msg_gps.py --remote-address 127.0.0.1 --remote-port 1516 --local-port 5398 --gps-port 5999 --send-custom
```

This runs `V2XInterface` (decoding received BSMs and `ITTCustomMessage` payloads) together
with `GpsPositionInterface` (decoding fixed-format GPS position packets). Pass `--send-custom`
to also periodically send an example `ITTCustomMessage` (off by default). See [Using the Library in Your Application](#using-the-library-in-your-application) for details on both interfaces.

If PyQt6 is installed, `src/v2xintf_ex.py` starts the GUI demo. Otherwise, it runs in console mode.

## Notes

- Default local UDP port is `5398`.
- Default remote UDP endpoint is `127.0.0.1:1516`.
- Use `Ctrl+C` to stop a running example.
