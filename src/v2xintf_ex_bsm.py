import time
import argparse
from pprint import pformat
from typing import Any

from v2xintf import V2XInterface, WAVE_MSG_IDS
from j2735_asn import compile_j2735_spec


j2735_spec = None

def get_msg_info(msg_id: int):
        for entry in WAVE_MSG_IDS:
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


def test_callback(data: bytes, msg_id: int):
    msg_info = get_msg_info(msg_id)
    msg_name = "Unknown"
    if msg_info is not None:
        msg_name = msg_info["name"]
                
    print(f"Received packet: {len(data)} bytes, {msg_name} (Message ID: {msg_id}).")
    mf = j2735_spec.decode("MessageFrame", data)
    if msg_id == 20:  # BSM
        bsm = j2735_spec.decode("BasicSafetyMessage", mf["value"])
        formatted_bsm = _normalize_for_print(bsm)
        print(_format_bsm_summary(bsm))
        print(f"Decoded BasicSafetyMessage:\n{pformat(formatted_bsm, width=120, sort_dicts=False)}\n")

        # TODO : Use bsm values to extract and print the vehicle's BSM 
            


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V2XInterface Example")
    parser.add_argument("--remote-address", type=str, default="127.0.0.1", help="Remote IP address (default: 127.0.0.1)")
    parser.add_argument("--remote-port", type=int, default=1516, help="Remote UDP port (default: 1516)")
    parser.add_argument("--local-port", type=int, default=5398, help="Local UDP port (default: 5398)")
    args = parser.parse_args()

    setup_j2735_spec()
    print(f"Starting V2XInterface (BSM parser) on port {args.local_port}...")

    v2x_interface = V2XInterface(callback=test_callback, remote_address=args.remote_address, remote_port=args.remote_port, local_port=args.local_port)
    v2x_interface.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping receiver...")
        v2x_interface.stop()
        print("Done.")
