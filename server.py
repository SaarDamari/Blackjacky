import socket
import threading
import time
import random
import datetime
import protocol

# --- Server Configuration ---
SERVER_IP_BIND = '0.0.0.0' # Listen on all interfaces
BROADCAST_PORT = 13122     # Fixed UDP port per requirements
BUFFER_SIZE = 1024
WATCHDOG_TIMEOUT = 30      # Seconds before resetting stuck barriers
ANIMATION_DELAY = 0.8      # Delay for card reveal effect
ROUND_COOLDOWN = 2.0       # Delay between rounds

def log(msg):
    """Prints timestamped log messages with thread name for debugging."""
    t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    t_name = threading.current_thread().name
    print(f"[{t}] [{t_name}] {msg}")

# --- Game Logic Classes ---
class Card:
    """Represents a single playing card."""
    def __init__(self, rank, suit):
        self.rank, self.suit = rank, suit
    
    def get_struct_values(self):
        """Converts card to protocol integer values."""
        rm = {'A':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13}
        sm = {'♠':0,'♥':1,'♦':2,'♣':3}
        return rm[self.rank], sm[self.suit]
    
    def get_value(self):
        """Calculates Blackjack value (J/Q/K = 10, A = 11 initially)."""
        if self.rank in ['J','Q','K']: return 10
        if self.rank == 'A': return 11
        return int(self.rank)
    
    def __str__(self): return f"{self.rank}{self.suit}"

class SharedDeck:
    """Thread-safe deck of cards."""
    def __init__(self):
        self.cards = []
        self.lock = threading.Lock()
        self.fill_deck()
    
    def fill_deck(self):
        self.cards = [Card(r,s) for s in ['♠','♥','♦','♣'] for r in ['2','3','4','5','6','7','8','9','10','J','Q','K','A']]
        random.shuffle(self.cards)
        log(f"[DECK] 🔥 SHUFFLED! Cards: {len(self.cards)}")
    
    def deal(self):
        with self.lock:
            if not self.cards: self.fill_deck()
            return self.cards.pop()

class Hand:
    """Manages a player's or dealer's hand."""
    def __init__(self): self.cards = []
    
    def add_card(self, c): self.cards.append(c)
    
    def get_value(self):
        """Calculates best hand value (handles Aces)."""
        v, a = 0, 0
        for c in self.cards:
            v += c.get_value()
            if c.rank=='A': a+=1
        while v>21 and a>0: v-=10; a-=1
        return v
    
    def clear(self): self.cards = []

GLOBAL_DECK = SharedDeck()

# --- Room Management (Synchronization Core) ---
class DynamicGameRoom:
    """
    Manages client synchronization using Barriers.
    Handles dynamic joining (Lobby) and round state.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.active_players = []
        self.waiting_players = []
        self.game_in_progress = False
        self.lobby_condition = threading.Condition(self.lock)
        
        # Barrier for synchronizing all active threads at each game step
        self.barrier = threading.Barrier(1)
        self.barrier_id = 0
        
        self.dealer_hand = Hand()
        self.global_round_id = 1       
        self.new_round_pending = True 
        
        self.dealer_playing_lock = threading.Lock()
        self.dealer_played_flag = False
        
        # Watchdog data
        self.last_activity_time = time.time()
        self.current_step_name = "Init"

    def touch_watchdog(self, step):
        """Updates the timestamp to prevent Watchdog timeout."""
        self.last_activity_time = time.time()
        self.current_step_name = step

    def join_lobby(self, player_id, player_name):
        """
        Handles player entry. 
        If game is idle -> Join immediately.
        If game is active -> Wait in lobby until round ends.
        """
        with self.lobby_condition:
            if not self.game_in_progress:
                self.active_players.append(player_id)
                log(f"[LOBBY] Joined IMMEDIATELY. Active: {len(self.active_players)}")
                self.recreate_barrier("Player Joined")
                return False 
            else:
                log(f"[LOBBY] Game running -> QUEUED. Waiting for next round...")
                self.waiting_players.append(player_id)
                self.lobby_condition.wait() # Blocking wait - No busy waiting
                log(f"[LOBBY] WOKE UP! Joining active game now.")
                return True 

    def player_disconnect(self, player_id):
        """Safely removes player and resets barrier if needed."""
        with self.lock:
            log(f"[DISCONNECT] Cleaning up player...")
            if player_id in self.active_players:
                self.active_players.remove(player_id)
                if len(self.active_players) > 0:
                    self.new_round_pending = True
                    try: self.barrier.abort() 
                    except: pass
            
            if player_id in self.waiting_players:
                self.waiting_players.remove(player_id)
            
            if len(self.active_players) == 0:
                log("[RESET] Room empty. Full Reset.")
                self.game_in_progress = False
                self.dealer_hand.clear()
                self.global_round_id = 1
                self.new_round_pending = True

    def start_round_mark(self):
        with self.lock: 
            if not self.game_in_progress: self.game_in_progress = True

    def try_advance_round(self, current_round_from_thread):
        """Checks if global round counter needs incrementing."""
        with self.lock:
            if self.global_round_id == current_round_from_thread:
                self.global_round_id += 1
                self.new_round_pending = True
                self.dealer_played_flag = False
                log(f"[GAME] >>> ADVANCING to Round {self.global_round_id}. Reset Pending=True <<<")
                return True
            return False

    def merge_waiting_players(self):
        """Moves waiting players to active list."""
        with self.lobby_condition:
            if self.waiting_players:
                log(f"[LOBBY] Merging {len(self.waiting_players)} waiting players.")
                self.active_players.extend(self.waiting_players)
                self.waiting_players.clear()
                time.sleep(0.1) 
            self.recreate_barrier("Merge/New Round")
            self.lobby_condition.notify_all()

    def recreate_barrier(self, reason):
        if len(self.active_players) > 0:
            self.barrier = threading.Barrier(len(self.active_players))
            self.barrier_id += 1
            log(f"[BARRIER-NEW #{self.barrier_id}] Reason: '{reason}'. Size: {self.barrier.parties}")

    def wait_at_barrier(self, step_name):
        """
        Synchronizes threads. Returns barrier index.
        Includes timeout handling to prevent deadlocks.
        """
        self.touch_watchdog(step_name)
        while True:
            with self.lock:
                curr_bar = self.barrier
                curr_id = self.barrier_id
            try:
                idx = curr_bar.wait(timeout=WATCHDOG_TIMEOUT)
                return idx
            except threading.BrokenBarrierError:
                with self.lock:
                    if self.barrier_id != curr_id: continue 
                    if len(self.active_players) == 0: return -1
                    log(f"[BARRIER] 💥 Broken Barrier detected! Fixing...")
                    self.recreate_barrier("Fix Broken")
            except threading.BarrierError:
                log(f"[WATCHDOG] ⏰ Barrier TIMEOUT at '{step_name}'! Forcing break.")
                with self.lock:
                     try: self.barrier.abort()
                     except: pass

ROOM = DynamicGameRoom()

def watchdog_loop():
    """Monitors game state and resets barriers if threads get stuck."""
    log("[WATCHDOG] Started monitoring...")
    while True:
        time.sleep(5)
        now = time.time()
        if len(ROOM.active_players) > 0 and (now - ROOM.last_activity_time > WATCHDOG_TIMEOUT + 5):
            log(f"[WATCHDOG] ⚠️ SYSTEM STUCK at '{ROOM.current_step_name}'! Kicking barrier...")
            with ROOM.lock:
                try: ROOM.barrier.abort()
                except: pass
            ROOM.touch_watchdog("WatchdogReset")

# --- Network Handlers ---
def udp_broadcast_thread(tcp_listening_port):
    """Broadcasts server availability via UDP for client discovery."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    packet = protocol.pack_offer(tcp_listening_port, "SaarServer")
    
    while True:
        try: 
            s.sendto(packet, ('<broadcast>', BROADCAST_PORT))
            time.sleep(1)
        except: 
            time.sleep(1)

def handle_client(sock, addr):
    """Handles a single client connection - manages rounds and game flow."""
    my_id = threading.get_ident()
    log(f"[NET] Connection from {addr}")
    
    try:
        data = sock.recv(BUFFER_SIZE)
        parsed = protocol.unpack_request(data)
        if not parsed: return
        rounds_wanted, name = parsed
        threading.current_thread().name = name
        
        log(f"[NET] {name} wants {rounds_wanted} rounds.")
        waited_in_lobby = ROOM.join_lobby(my_id, name)
        
        if waited_in_lobby:
            log(f"[{name}] Syncing with End-Of-Round barrier...")
            ROOM.wait_at_barrier("Lobby-Merge-Sync")

        played_rounds = 0
        while played_rounds < rounds_wanted:
            ROOM.start_round_mark()
            with ROOM.lock: my_current_round = ROOM.global_round_id
            round_lbl = f"R{my_current_round}"

            # 1. Round Start Synchronization
            idx = ROOM.wait_at_barrier(f"{round_lbl} Start")
            if idx == -1: break
            
            if idx == 0:
                with ROOM.lock:
                    if ROOM.new_round_pending:
                        log(f"[DEALER] >>> RESET & DEAL for Round {ROOM.global_round_id} <<<")
                        ROOM.dealer_hand.clear()
                        ROOM.dealer_hand.add_card(GLOBAL_DECK.deal())
                        ROOM.dealer_hand.add_card(GLOBAL_DECK.deal())
                        ROOM.new_round_pending = False

            # 2. Distribute Initial Cards
            if ROOM.wait_at_barrier(f"{round_lbl} Post-Deal-Logic") == -1: break
            try: sock.send(b"SRT") 
            except: pass

            my_dealer_visible_card = ROOM.dealer_hand.cards[0]
            p_hand = Hand()
            c1, c2 = GLOBAL_DECK.deal(), GLOBAL_DECK.deal()
            p_hand.add_card(c1); p_hand.add_card(c2)

            for c in [c1, c2]: sock.send(protocol.pack_server_card(0, *c.get_struct_values()))
            sock.send(protocol.pack_server_card(0, *my_dealer_visible_card.get_struct_values()))
            
            try: sock.recv(3) # Wait for RDY
            except: pass

            # 3. Synchronize Display (Wait for everyone to load images)
            if ROOM.wait_at_barrier(f"{round_lbl} DISPLAY-SYNC") == -1: break
            try: sock.send(b"GO_")
            except: pass

            # 4. Player Turn Loop
            p_bust = False
            sock.settimeout(WATCHDOG_TIMEOUT) 
            try:
                while True:
                    ROOM.touch_watchdog(f"{name} is thinking...") 
                    pkt = sock.recv(BUFFER_SIZE)
                    if len(pkt) < 10: break
                    ROOM.touch_watchdog(f"{name} acted!")
                    
                    # Robust command handling
                    raw_cmd = pkt[5:10].decode('utf-8', errors='ignore')
                    clean_cmd = raw_cmd.strip('\x00').strip().upper()

                    if "HIT" in clean_cmd:
                        log(f"[{name}] HIT")
                        nc = GLOBAL_DECK.deal(); p_hand.add_card(nc)
                        sock.send(protocol.pack_server_card(2 if p_hand.get_value()>21 else 0, *nc.get_struct_values()))
                        if p_hand.get_value()>21: p_bust=True; break
                    elif "STAND" in clean_cmd: 
                        log(f"[{name}] STAND")
                        break
            except socket.timeout:
                log(f"[{name}] ⏰ AFK KICK!")
                return 
            finally:
                sock.settimeout(None) 

            # 5. Dealer Turn (Only one thread executes this)
            idx = ROOM.wait_at_barrier(f"{round_lbl} Pre-Dealer")
            if idx == -1: break

            with ROOM.dealer_playing_lock:
                if not ROOM.dealer_played_flag:
                    ROOM.dealer_played_flag = True
                    dv = ROOM.dealer_hand.get_value()
                    log(f"[DEALER] Playing. Start: {dv}")
                    while dv < 17:
                        nc = GLOBAL_DECK.deal()
                        ROOM.dealer_hand.add_card(nc)
                        dv = ROOM.dealer_hand.get_value()
                        log(f"[DEALER] Drew {nc}. New: {dv}")
                    log(f"[DEALER] Finished at {dv}")

            # 6. Result Calculation
            if ROOM.wait_at_barrier(f"{round_lbl} Post-Dealer") == -1: break

            dv = ROOM.dealer_hand.get_value()
            pv = p_hand.get_value()
            res = 2 # Default Loss
            if p_bust: res = 2
            elif dv > 21: res = 3
            elif pv > dv: res = 3
            elif pv == dv: res = 1

            if not p_bust:
                cards_to_reveal = ROOM.dealer_hand.cards[1:]
                for c in cards_to_reveal:
                    sock.send(protocol.pack_server_card(0, *c.get_struct_values()))
                    time.sleep(ANIMATION_DELAY) 
                
                if cards_to_reveal:
                    last = cards_to_reveal[-1]
                    sock.send(protocol.pack_server_card(res, *last.get_struct_values()))
                else:
                    sock.send(protocol.pack_server_card(res, *my_dealer_visible_card.get_struct_values()))
            else:
                sock.send(protocol.pack_server_card(2, *my_dealer_visible_card.get_struct_values()))

            played_rounds += 1
            log(f"[{name}] Finished {played_rounds}/{rounds_wanted}")

            # 7. End of Round Cleanup & Cooldown
            did_advance = ROOM.try_advance_round(my_current_round)
            if did_advance:
                ROOM.merge_waiting_players()
            
            if ROOM.wait_at_barrier(f"{round_lbl} Post-Merge") == -1: break
            time.sleep(ROUND_COOLDOWN) 

    except Exception as e: log(f"[Err {name}] {e}")
    finally:
        ROOM.player_disconnect(my_id)
        try: sock.close()
        except: pass

def main():
    """Entry point - starts watchdog, TCP server, and UDP broadcaster."""
    wd = threading.Thread(target=watchdog_loop, daemon=True)
    wd.start()
    
    # Dynamic Port Assignment
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind((SERVER_IP_BIND, 0))
    srv.listen(5)
    
    _, dynamic_port = srv.getsockname()
    
    udp_t = threading.Thread(target=udp_broadcast_thread, args=(dynamic_port,), daemon=True)
    udp_t.start()

    hostname = socket.gethostname()
    try: local_ip = socket.gethostbyname(hostname)
    except: local_ip = '127.0.0.1'

    print(f"Server started, listening on IP address {local_ip} (Port {dynamic_port})")

    try:
        while True:
            c, a = srv.accept()
            t = threading.Thread(target=handle_client, args=(c, a))
            t.daemon = True
            t.start()
    except KeyboardInterrupt: pass
    finally: srv.close()

if __name__ == "__main__":
    main()