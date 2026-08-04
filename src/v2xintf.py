"""!
@file v2xintf.py
@brief V2X Interface module for handling DSRC message communication over UDP.
"""
from ast import Add
import socket
import threading
import time
from typing import Optional, Callable

WAVE_MSG_IDS = [
    {
        "name" : "BSM",
        "psid" : "0020",
        "dsrc_msg_id" : "20",
        "channel" : "183",
        "priority" :  "6"
    },
    {
        "name" : "MAP",
        "psid" : "0082",
        "dsrc_msg_id" : "18",
        "channel" : "183",
        "priority" : "3"
    },
    # {
    #     "name" : "SPAT",
    #     "psid" : "0082",
    #     "dsrc_msg_id" : "19",
    #     "channel" : "183",
    #     "priority" : "3"
    # },
    {
        "name" : "TIM",
        "psid" : "0083",
        "dsrc_msg_id" : "31",
        "channel" : "183",
        "priority" : "3"
    },
    {
        "name" : "PSM",
        "psid" : "0027",
        "dsrc_msg_id" : "32",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "SensorDataSharingMessage",
        "psid" : "8010",
        "dsrc_msg_id" : "41",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "MobilityRequest",
        "psid" : "BFEE",
        "dsrc_msg_id" : "240",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "MobilityResponse",
        "psid" : "BFEE",
        "dsrc_msg_id" : "241",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "MobilityOperation",
        "psid" : "BFEE",
        "dsrc_msg_id" : "243",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "MobilityPath",
        "psid" : "BFEE",
        "dsrc_msg_id" : "242",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "TrafficControlRequest",
        "psid" : "8003",
        "dsrc_msg_id" : "244",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "TrafficControlMessage",
        "psid" : "8003",
        "dsrc_msg_id" : "245",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "EmergencyVehicleResponse",
        "psid" : "8005",
        "dsrc_msg_id" : "246",
        "channel" : "183",
        "priority" : "6"
    },
    {
        "name" : "EmergencyVehicleAck",
        "psid" : "8005",
        "dsrc_msg_id" : "247",
        "channel" : "183",
        "priority" : "6"
    }
]

class V2XInterface:
    """!
    @brief Interface for managing V2X message transmission and reception over UDP.
    
    @details This class handles listening for incoming V2X messages on a local UDP port
    in a background thread, and provides methods to pack and send outgoing messages
    to a remote UDP endpoint.
    """

    def __init__(self, callback: Callable[[bytes, int], None], remote_address: str = "127.0.0.1", remote_port: int = 1516, local_port: int = 5398, check_validity: bool = True):
        """!
        @brief Initializes the V2XInterface.
        
        @param callback A callable function invoked when a valid message is received. Takes (data: bytes, msg_id: int).
        @param remote_address The remote IP address to send V2X messages to.
        @param remote_port The remote UDP port to send V2X messages to.
        @param local_port The local UDP port to listen on for incoming messages.
        @param check_validity Whether to check the validity of received messages.
        """
        self.remote_address = remote_address
        self.remote_port = remote_port
        self.local_port = local_port
        self.callback = callback
        self.check_validity = check_validity
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # WAVE Service Advertisement (WSA) frame size = 1 byte for J2735 payloads < 128 bytes. IEEE 1609.3 (2020) - 8.1.3.
        # Add 2 bytes for DSRCmsgID.
        self.short_frame_ = 3

        # WAVE Service Advertisement (WSA) frame size = 2 bytes for J2735 payloads > 127 bytes. IEEE 1609.3 (2020) - 8.1.3.
        # Add 2 bytes for DSRCmsgID.
        self.long_frame_ =4

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
            # print(f"Error binding to {self.remote_address}:{self.local_port} - {e}")
            return

        sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data, _ = sock.recvfrom(65535)
                # print(f"from {address[0]}:{address[1]} -> {self.local_port} : {len(data)} bytes")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving data: {e}")
                continue

            self.onV2XMessageReceived(data)

        sock.close()

    def find_msg_info_by_name(self, name: str):
        """!
        @brief Looks up a WAVE_MSG_IDS entry by its message type name.

        @param name The message type name (e.g., 'BSM', 'SensorDataSharingMessage').
        @return Dictionary containing message info if found, otherwise None.
        """
        for entry in WAVE_MSG_IDS:
            if entry["name"] == name:
                return entry
        return None

    def is_valid_msg_id(self, msg_id: int):
        """!
        @brief Checks if a given message ID exists in the known WAVE_MSG_IDS list.
        
        @param msg_id The DSRC message ID as an integer.
        @return Dictionary containing message info if valid, otherwise None.
        """
        for entry in WAVE_MSG_IDS:
            if int(entry["dsrc_msg_id"]) == msg_id:
                return entry
        return None

    def is_possible_psid(self, msg_id: str) -> bool:
        """!
        @brief Checks if a given Provider Service Identifier (PSID) is known.
        
        @param msg_id The string representation of the parsed message ID.
        @return True if the PSID matches an entry in WAVE_MSG_IDS, False otherwise.
        """
        for entry in WAVE_MSG_IDS:
            psid_value = int(entry["psid"],16)
            psid_int = str(psid_value)
            print(f"Checking if received message is possibly PSID: {msg_id} / {psid_int}")
            if msg_id == psid_int :
                return True
        print(f"Received message is not a known PSID: {msg_id}")
        return False

    def is_valid_msg_size(self, msg_vec: bytes, start_index: int, entry: bytes):
        """!
        @brief Validates the size of the message frame.
        
        @param msg_vec The sub-array of bytes representing the message.
        @param start_index The starting index of the message in the original entry.
        @param entry The original raw byte array.
        @return True if the message size is valid, False otherwise.
        """
        if len(msg_vec) > 127 :
            tmp_start_index = start_index + self.long_frame_
            long_vec = entry[tmp_start_index:]
            msg_size = (msg_vec[2] & 0x7F) << 8 | msg_vec[3]
            if msg_size == len(long_vec) :
                return True
            else :
                # print(f"expected size: {msg_size}, actual size: {len(long_vec)}")
                return False
        elif len(msg_vec) < 128 and len(msg_vec) > 3 :
            tmp_start_index = start_index + self.short_frame_
            short_vec = entry[tmp_start_index:]
            msg_size = msg_vec[2]
            if msg_size == len(short_vec) :
                return True
            else :
                # print(f"expected size: {msg_size}, actual size: {len(short_vec)}")
                return False
        else :
            # print(f"expected size: {len(msg_vec)}")
            return False

    def is_valid_msg_assuming_bsm_psid(self, start_index, entry: bytes):
        """!
        @brief Validates the message structure assuming it starts with a BSM PSID.
        
        @param start_index The starting index in the byte array.
        @param entry The original raw byte array.
        @return True if valid BSM identifiers are found, False otherwise.
        """
        if start_index < 0 or start_index >= len(entry)-1 :
            print(f"Error: invalid start index {start_index} for data length {len(entry)}")
            return False
    
        # Valid element id will exist, at max, 5 bytes after a PSID
        for i in range(start_index, min(start_index + 6, len(entry)-1)) :
            # Generate a 16-bit element id from two bytes, e.g. [03 128 ...] = 0x0380
            element_id = (int(entry[i]) << 8) | int(entry[i + 1])
            # Check if valid element id 896 (0x0380) exists after PSID and before DSRCmsgID
            if element_id == 896 :
                element_id_index = i
                # Valid DSRCmsgID will exist, at max, 5 bytes after the element id
                print(f"Found valid element id 896 at index {element_id_index}, checking for DSRCmsgID 20...")
                for j in range(element_id_index, min(element_id_index + 6, len(entry) - 1)):
                    # Generate a 16-bit message id from two bytes, e.g. [0x00, 0x14] = 0x0014
                    possible_msg_id = (int(entry[j]) << 8) | int(entry[j + 1])

                    # Check if BSM DSRCmsgID 20 (0x0014)
                    if possible_msg_id == 20:
                        print(f"Found valid DSRCmsgID 20 at index {j}, message is valid BSM.")
                        return True
        print("No valid DSRCmsgID 20 found after element id 896, message is not valid BSM.")
        return False

    def onV2XMessageReceived(self, data: bytes) -> None:
        """!
        @brief Callback invoked when raw V2X data is received over the UDP socket.
        
        @param data The raw bytes received from the network.
        """
        if not data or len(data) < 3 :
            # print(f"Received empty or invalid packet: len={len(data)} bytes")
            return
        valid_msg_done = False
        
        if self.check_validity :
            for i in range(len(data)-3) :
                msg_id = (data[i] << 8) | data[i+1]
                msg_info = self.is_valid_msg_id(msg_id)
                if msg_info is None:
                    # print(f"discarding received message with unknown DSRCmsgID: {msg_id}")
                    continue
                if ((i + self.short_frame_) >= len(data)) :
                    # print("discarding received message with insufficient data for short frame header.")
                    break; # Break if not enough data remaining

                start_index = i
                msg_vec = data[start_index:]
                if len(msg_vec) > 16383 :
                    # print("discarding received message with length field longer than 16383.")
                    break; # Break if message length exceeds max allowed

                if self.is_valid_msg_size(msg_vec, start_index, data) == False:
                    # print(f"discarding received message with invalid size field: {msg_id}")
                    continue
                
                if self.callback:
                    self.callback(data, msg_id)
                    valid_msg_done = True
                    break

        if not valid_msg_done :
            # User callback should take care of any further validation if desired, but we will still call it with the raw data and None for msg_id.
            if self.callback:
                self.callback(data, None)

    def to_hex_string(self, data) -> str:
        """!
        @brief Converts a byte array to a continuous hexadecimal string.
        
        @param data The bytes to convert.
        @return The hexadecimal string representation of the data.
        """
        return "".join(f"{b:02x}" for b in data)

    def pack_message(self, data:bytes, message_type:str) -> bytes:
        """!
        @brief Packs raw bytes into a formatted string envelope for transmission.
        
        @param data The raw DSRC payload bytes.
        @param message_type The string name of the message type (e.g., 'BSM', 'MAP').
        @return The UTF-8 encoded byte array of the formatted text envelope.
        """
        if not data :
            raise ValueError("pack_message requires non-empty data")

        msg_info = self.find_msg_info_by_name(message_type)

        if msg_info :
            ifm_msg_name = msg_info['name']
            ifm_channel = msg_info['channel']
            ifm_priority = msg_info['priority']
            ifm_psid = msg_info['psid']
        else :
            if len(data) < 2 :
                raise ValueError(f"pack_message requires at least 2 bytes of data to infer an unknown message ID, got {len(data)}")
            msg_id = (data[0] << 8) | data[1]
            # print(f"No WAVE config entry for type: {message_type}, using defaults for ID {msg_id}")
            ifm_msg_name = message_type
            ifm_channel = "CCH"
            ifm_priority = "1"
            ifm_psid = str(msg_id)

        lines = [
            "Version=0.7",
            f"Type={ifm_msg_name}",
            f"PSID={ifm_psid}",
            f"Priority={ifm_priority}",
            "TxMode=ALT",
            f"TxChannel={ifm_channel}",
            "TxInterval=0",
            "DeliveryStart=",
            "DeliveryStop=",
            "Signature=False",
            "Encryption=False",
            f"Payload={self.to_hex_string(data)}",
        ]
        text = "\n".join(lines) + "\n"
        return text.encode("utf-8")

    def sendV2XMessage(self, data: bytes, message_type:str="Unknown") -> None:
        """!
        @brief Packs and sends a V2X message to the remote target via UDP.
        
        @param data The raw DSRC payload to send.
        @param message_type The string identifying the message type.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            packed_message = self.pack_message(data, message_type)
            # print(f"Send message to {self.remote_address}:{self.remote_port}")
            sock.sendto(packed_message, (self.remote_address, self.remote_port))
        except (ValueError, OSError) as e:
            print(f"Error sending message: {e}")
        finally:
            sock.close()

        return
