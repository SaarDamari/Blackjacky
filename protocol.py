import struct

# Protocol constants for client-server communication
MAGIC_COOKIE = 0xabcddcba
MSG_OFFER = 0x02
MSG_REQUEST = 0x03
MSG_PAYLOAD = 0x04

SERVER_NAME_LEN = 32
TEAM_NAME_LEN = 32
CLIENT_CMD_LEN = 5

# Format Strings for struct.pack
# ! = Network Endian (Big Endian)
# I=4, B=1, H=2, s=string
FMT_OFFER = f'!IBH{SERVER_NAME_LEN}s'    # 4+1+2+32 = 39 bytes
FMT_REQUEST = f'!IBB{TEAM_NAME_LEN}s'    # 4+1+1+32 = 38 bytes
FMT_CMD = f'!IB{CLIENT_CMD_LEN}s'        # 4+1+5 = 10 bytes
FMT_CARD = '!IBBHB'                      # 4+1+1+2+1 = 9 bytes

def pack_offer(server_port, server_name):
    """
    Packs a UDP offer message from the server.
    Format: Cookie, Type(0x2), Port, ServerName(32).
    """
    try:
        # Pad or truncate server name to exactly 32 bytes
        name_bytes = server_name.encode('utf-8')[:SERVER_NAME_LEN].ljust(SERVER_NAME_LEN, b'\x00')
        return struct.pack(FMT_OFFER, MAGIC_COOKIE, MSG_OFFER, server_port, name_bytes)
    except Exception:
        return None

def unpack_offer(data):
    """
    Unpacks a UDP offer message. Returns (port, server_name) or None if invalid.
    """
    try:
        expected_len = struct.calcsize(FMT_OFFER)
        if len(data) < expected_len:
            return None
        
        cookie, msg_type, port, name_bytes = struct.unpack(FMT_OFFER, data[:expected_len])
        
        if cookie != MAGIC_COOKIE or msg_type != MSG_OFFER:
            return None
            
        server_name = name_bytes.decode('utf-8').strip('\x00').strip()
        return (port, server_name)
    except Exception:
        return None

def pack_request(num_rounds, team_name):
    """
    Packs a TCP request message from the client.
    Format: Cookie, Type(0x3), Rounds, TeamName(32).
    """
    try:
        name_bytes = team_name.encode('utf-8')[:TEAM_NAME_LEN].ljust(TEAM_NAME_LEN, b'\x00')
        return struct.pack(FMT_REQUEST, MAGIC_COOKIE, MSG_REQUEST, num_rounds, name_bytes)
    except Exception:
        return None

def unpack_request(data):
    """
    Unpacks a TCP request. Returns (rounds, team_name) or None if invalid.
    """
    try:
        expected_len = struct.calcsize(FMT_REQUEST)
        if len(data) < expected_len:
            return None
            
        cookie, msg_type, rounds, name_bytes = struct.unpack(FMT_REQUEST, data[:expected_len])
        
        if cookie != MAGIC_COOKIE or msg_type != MSG_REQUEST:
            return None
            
        team_name = name_bytes.decode('utf-8').strip('\x00').strip()
        return (rounds, team_name)
    except Exception:
        return None

def pack_client_decision(decision):
    """
    Packs the client's gameplay decision ("Hittt" or "Stand").
    """
    try:
        cmd = ""
        if "HIT" in decision.upper():
            cmd = "Hittt"
        elif "STAND" in decision.upper():
            cmd = "Stand"
        else:
            return None
            
        return struct.pack(FMT_CMD, MAGIC_COOKIE, MSG_PAYLOAD, cmd.encode('utf-8'))
    except Exception:
        return None

def pack_server_card(result_code, card_rank, card_suit):
    """
    Packs the server's card/result message.
    """
    try:
        return struct.pack(FMT_CARD, MAGIC_COOKIE, MSG_PAYLOAD, result_code, card_rank, card_suit)
    except Exception:
        return None

def unpack_server_message(data):
    """
    Unpacks the server's message. Returns (result, rank, suit) or None.
    """
    try:
        expected_len = struct.calcsize(FMT_CARD)
        if len(data) < expected_len:
            return None
            
        cookie, msg_type, result, rank, suit = struct.unpack(FMT_CARD, data[:expected_len])
        
        if cookie != MAGIC_COOKIE:
            return None
        return (result, rank, suit)
    except Exception:
        return None