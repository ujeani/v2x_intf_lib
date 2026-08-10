"""!
@file v2xintf_ex_bsm_gps.py
@brief Example running V2XInterface (BSM parsing) and GpsPositionInterface together.

@details This extends v2xintf_ex_bsm.py by additionally starting a
GpsPositionInterface that listens for fixed-format binary GPS position
messages (Timestamp/Latitude/Longitude/Speed/Direction) on UDP port 5999,
independently of the DSRC/J2735 messages handled by V2XInterface.
"""
import time
import struct
import threading
import argparse
from pprint import pformat
from typing import Any, Optional

from v2xintf import V2XInterface, WAVE_MSG_IDS, ITT_CUSTOM_MSG_IDS
from gps_intf import GpsPositionInterface, GpsPosition, DEFAULT_GPS_PORT
from j2735_asn import compile_j2735_spec

CUSTOM_MSG_ID = int(next(e for e in ITT_CUSTOM_MSG_IDS if e["name"] == "ITTCustomMessage")["dsrc_msg_id"]) # 254

DEV_ID = 0xF0E1D2C3  # Example device ID for Custom messages

# ITTCustomMessage wire format (msg_id 254), expressed as the equivalent C
# struct. msg_id is mandatory and must come first; the remaining fields are
# an example payload that _parse_custom_message() below decodes to match.
# struct {
#     short unsigned int msg_id; // 2 bytes, unsigned 16-bit integer (Mandatory), use 254 for ITTCustomMessage
#     // Design your message format
#     unsigned int device_id; // 4 bytes, unsigned 32-bit integer
#     unsigned char counter1; // 1 byte, unsigned 8-bit integer
#     unsigned char counter2; // 1 byte, unsigned 8-bit integer
#     unsigned short int counter3; // 2 bytes, unsigned 16-bit integer
# }

# Network byte order (big-endian), matching the msg_id parsing done in
# V2XInterface.onV2XMessageReceived (data[i] << 8 | data[i+1]).
CUSTOM_MSG_FORMAT = ">HIBBH"
CUSTOM_MSG_SIZE = struct.calcsize(CUSTOM_MSG_FORMAT)


j2735_spec = None

def get_msg_info(msg_id: int):
        for entry in WAVE_MSG_IDS:
            if int(entry["dsrc_msg_id"]) == msg_id:
                return entry

        for entry in ITT_CUSTOM_MSG_IDS:
            if int(entry["dsrc_msg_id"]) == msg_id:
                return entry

        return None

def setup_j2735_spec():
    global j2735_spec
    j2735_spec = compile_j2735_spec()


def _normalize_for_print(value: Any):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {k: _normalize_for_print(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_print(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_normalize_for_print(v) for v in value)
    return value


def _format_bsm_summary(bsm: dict[str, Any]) -> str:
    core = bsm.get("coreData", {})

    lat_raw = core.get("lat")
    lon_raw = core.get("long")
    speed_raw = core.get("speed")
    heading_raw = core.get("heading")
    vehicle_id = core.get("id")

    lat_deg = lat_raw / 10_000_000 if isinstance(lat_raw, int) else None
    lon_deg = lon_raw / 10_000_000 if isinstance(lon_raw, int) else None
    speed_mps = speed_raw * 0.02 if isinstance(speed_raw, int) else None
    heading_deg = heading_raw * 0.0125 if isinstance(heading_raw, int) else None

    vehicle_id_text = vehicle_id.hex() if isinstance(vehicle_id, bytes) else str(vehicle_id)

    return (
        "BSM Summary:\n"
        f"  msgCnt      : {core.get('msgCnt')}\n"
        f"  id          : {vehicle_id_text}\n"
        f"  lat/lon     : {lat_raw} / {lon_raw}"
        + (f" ({lat_deg:.7f}, {lon_deg:.7f})" if lat_deg is not None and lon_deg is not None else "")
        + "\n"
        f"  speed       : {speed_raw}"
        + (f" ({speed_mps:.2f} m/s)" if speed_mps is not None else "")
        + "\n"
        f"  heading     : {heading_raw}"
        + (f" ({heading_deg:.2f} deg)" if heading_deg is not None else "")
        + "\n"
        f"  transmission: {core.get('transmission')}\n"
    )


def _parse_custom_message(data: bytes):
    if len(data) < CUSTOM_MSG_SIZE:
        print(f"  Discarding: expected at least {CUSTOM_MSG_SIZE} bytes, got {len(data)}.")
        return

    msg_id, device_id, counter1, counter2, counter3 = struct.unpack_from(CUSTOM_MSG_FORMAT, data)

    print(
        "ITTCustomMessage:\n"
        f"  msg_id   : {msg_id}\n"
        f"  device_id: 0x{device_id:08X}\n"
        f"  counter1 : {counter1}\n"
        f"  counter2 : {counter2}\n"
        f"  counter3 : {counter3}\n"
    )


def _send_custom_messages(v2x_interface: V2XInterface, interval_s: float = 1.0):
    counter1 = 0    # unsigned char: wraps 0..255
    counter2 = 100  # unsigned char: wraps 0..255, starting at 100
    counter3 = 200  # unsigned short int: wraps 0..65535, starting at 200

    while True:
        payload = struct.pack(CUSTOM_MSG_FORMAT, CUSTOM_MSG_ID, DEV_ID, counter1, counter2, counter3)
        v2x_interface.sendV2XMessage(payload, "ITTCustomMessage")
        print(
            f"Sent ITTCustomMessage: device_id=0x{DEV_ID:08X}, "
            f"counter1={counter1}, counter2={counter2}, counter3={counter3}"
        )

        counter1 = (counter1 + 1) % 256
        counter2 = (counter2 + 1) % 256
        counter3 = (counter3 + 1) % 65536

        time.sleep(interval_s)


def msg_callback(data: bytes, msg_id: int):
    if msg_id is None:
        print(f"Received packet: {len(data)} bytes, Unknown (Non-SAE message).")
        return
    
    msg_info = get_msg_info(msg_id)
    msg_name = "Unknown"
    if msg_info is not None:
        msg_name = msg_info["name"]

    print(f"Received packet: {len(data)} bytes, {msg_name} (Message ID: {msg_id}).")
    if msg_name == "ITTCustomMessage":
        print("Received ITTCustomMessage")
        _parse_custom_message(data)
        return
    else :
        print(f"Received standard SAE message: {msg_name} (Message ID: {msg_id})")
    #     mf = j2735_spec.decode("MessageFrame", data)
    #     if msg_id == 20:  # BSM
    #         bsm = j2735_spec.decode("BasicSafetyMessage", mf["value"])
    #         formatted_bsm = _normalize_for_print(bsm)
    #         print(_format_bsm_summary(bsm))
    #         print(f"Decoded BasicSafetyMessage:\n{pformat(formatted_bsm, width=120, sort_dicts=False)}\n")


def gps_callback(data: bytes, position: Optional[GpsPosition]):
    if position is None:
        # onGpsMessageReceived already logged the size mismatch.
        return

    print(
        "GPS Position:\n"
        f"  timestamp : {position.timestamp_ms} ms\n"
        f"  lat/lon   : {position.latitude_raw} / {position.longitude_raw}"
        f" ({position.latitude_deg:.7f}, {position.longitude_deg:.7f})\n"
        f"  speed     : {position.speed_raw} ({position.speed_mps:.2f} m/s)\n"
        f"  direction : {position.direction_raw} ({position.direction_deg:.4f} deg)\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V2XInterface (BSM) + GpsPositionInterface Example")
    parser.add_argument("--remote-address", type=str, default="127.0.0.1", help="Remote IP address for V2XInterface (default: 127.0.0.1)")
    parser.add_argument("--remote-port", type=int, default=1516, help="Remote UDP port for V2XInterface (default: 1516)")
    parser.add_argument("--local-port", type=int, default=5398, help="Local UDP port for V2XInterface (default: 5398)")
    parser.add_argument("--gps-port", type=int, default=DEFAULT_GPS_PORT, help=f"Local UDP port for GpsPositionInterface (default: {DEFAULT_GPS_PORT})")
    parser.add_argument("--send-custom", action="store_true", help="Send ITTCustomMessage every 1 second (default: False)")
    args = parser.parse_args()

    setup_j2735_spec()
    print(f"Starting V2XInterface (BSM parser) on port {args.local_port}...")
    v2x_interface = V2XInterface(callback=msg_callback, remote_address=args.remote_address, remote_port=args.remote_port, local_port=args.local_port)
    v2x_interface.start()

    print(f"Starting GpsPositionInterface on port {args.gps_port}...")
    gps_interface = GpsPositionInterface(callback=gps_callback, local_port=args.gps_port)
    gps_interface.start()

    if args.send_custom:
        print("Starting ITTCustomMessage sender (every 1s)...")
        custom_sender_thread = threading.Thread(target=_send_custom_messages, args=(v2x_interface,), daemon=True)
        custom_sender_thread.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping receivers...")
        v2x_interface.stop()
        gps_interface.stop()
        print("Done.")
