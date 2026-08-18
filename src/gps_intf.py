"""!
@file gps_intf.py
@brief Interface for receiving fixed-format GPS position messages over UDP.
"""
import socket
import struct
import threading
from dataclasses import dataclass
from typing import Optional, Callable

# Timestamp(UINT64,8) | Latitude(INT32,4) | Longitude(INT32,4) | Speed(UINT16,2) | Direction(UINT16,2)
GPS_MSG_STRUCT = ">QiiHH"
GPS_MSG_SIZE = struct.calcsize(GPS_MSG_STRUCT)  # 20 bytes

DEFAULT_GPS_PORT = 5999


@dataclass
class GpsPosition:
    """!
    @brief Parsed fields of a GPS position UDP message.
    """
    timestamp_ms: int    # Time read from GPS, in milliseconds
    latitude_raw: int    # Latitude, in units of 0.1 micro-degrees (J2735)
    longitude_raw: int   # Longitude, in units of 0.1 micro-degrees (J2735)
    speed_raw: int       # Speed, in units of 0.02 m/s (J2735)
    direction_raw: int   # Direction (relative to north), in units of 0.0125 degrees (J2735)

    @property
    def latitude_deg(self) -> float:
        """!@brief Latitude converted to decimal degrees."""
        return self.latitude_raw * 1e-7

    @property
    def longitude_deg(self) -> float:
        """!@brief Longitude converted to decimal degrees."""
        return self.longitude_raw * 1e-7

    @property
    def speed_mps(self) -> float:
        """!@brief Speed converted to meters/second."""
        return self.speed_raw * 0.02

    @property
    def direction_deg(self) -> float:
        """!@brief Direction converted to degrees from North."""
        return self.direction_raw * 0.0125


class GpsPositionInterface:
    """!
    @brief Receives fixed-format binary GPS position messages over UDP.

    @details Listens on a local UDP port (default 5999) in a background thread for
    big-endian binary packets in the following format, expected roughly once per second:

        Field       Type    Length  Content
        Timestamp   UINT64  8       GPS time read, msec
        Latitude    INT32   4       0.1 micro-degree units (J2735)
        Longitude   INT32   4       0.1 micro-degree units (J2735)
        Speed       UINT16  2       0.02 m/s units (J2735)
        Direction   UINT16  2       0.0125 deg units from North (J2735)

    This is independent of V2XInterface, which handles DSRC/J2735 message envelopes;
    both can run at the same time on their own local ports.
    """

    def __init__(self, callback: Callable[[bytes, Optional[GpsPosition]], None], local_port: int = DEFAULT_GPS_PORT):
        """!
        @brief Initializes the GpsPositionInterface.

        @param callback A callable invoked when a packet is received. Takes (data: bytes, position: Optional[GpsPosition]).
        position is None when the packet does not match the expected fixed size.
        @param local_port The local UDP port to listen on for incoming messages.
        """
        self.local_port = local_port
        self.callback = callback
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """!
        @brief Starts the UDP receiver thread.
        """
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """!
        @brief Stops the UDP receiver thread gracefully.
        """
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        """!
        @brief Internal background loop for receiving UDP packets.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", self.local_port))
        except Exception as e:
            print(f"Error binding to 0.0.0.0:{self.local_port} - {e}")
            return

        sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving data: {e}")
                continue

            self.onGpsMessageReceived(data)

        sock.close()

    def parse_message(self, data: bytes) -> Optional[GpsPosition]:
        """!
        @brief Parses raw bytes into a GpsPosition.

        @param data The raw bytes received from the network.
        @return A GpsPosition if data is exactly GPS_MSG_SIZE (20) bytes, otherwise None.
        """
        if len(data) != GPS_MSG_SIZE:
            return None

        timestamp_ms, lat_raw, lon_raw, speed_raw, direction_raw = struct.unpack(GPS_MSG_STRUCT, data)
        return GpsPosition(
            timestamp_ms=timestamp_ms,
            latitude_raw=lat_raw,
            longitude_raw=lon_raw,
            speed_raw=speed_raw,
            direction_raw=direction_raw,
        )

    def onGpsMessageReceived(self, data: bytes) -> None:
        """!
        @brief Callback invoked when raw GPS data is received over the UDP socket.

        @param data The raw bytes received from the network.
        """
        position = self.parse_message(data)
        if position is None:
            print(f"discarding received GPS packet with unexpected size: {len(data)} bytes (expected {GPS_MSG_SIZE})")

        if self.callback:
            self.callback(data, position)
