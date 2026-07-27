# v2x_intf_lib

IT Telecom V2X OBU/RSU interface library.

## Overview

This repository provides a Python UDP-based V2X interface and example programs for receiving and handling J2735-based message payloads.

## Repository Structure

- `src/v2xintf.py`: Core V2X interface implementation.
- `src/v2xintf_ex.py`: Basic example app (console mode, with optional PyQt6 demo UI).
- `src/v2xintf_ex_bsm.py`: BSM-focused example using ASN.1 tooling.
- `J2735SET_202409/`: ASN.1 module collection.

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

## Usage

Run the general interface example:

```bash
python src/v2xintf_ex.py --remote-address 127.0.0.1 --remote-port 1516 --local-port 5398
```

Run the BSM example:

```bash
python src/v2xintf_ex_bsm.py --remote-address 127.0.0.1 --remote-port 1516 --local-port 5398
```

If PyQt6 is installed, `src/v2xintf_ex.py` starts the GUI demo. Otherwise, it runs in console mode.

## Notes

- Default local UDP port is `5398`.
- Default remote UDP endpoint is `127.0.0.1:1516`.
- Use `Ctrl+C` to stop a running example.
