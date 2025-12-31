import tkinter as tk
from tkinter import messagebox, simpledialog
import socket
import threading
import protocol
import time
import queue
import sys

# --- הגדרות ---
UDP_PORT = 13122
MSG_SIZE = 9

class BlackjackClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎰 Blackjack - Final Perfected 🎰")
        self.root.geometry("900x750")
        self.root.configure(bg='#0d4d0d')

        self.running = True
        self.is_playing = False
        self.in_dialog = False
        self.tcp_socket = None
        self.user_action = None
        self.action_event = threading.Event()
        
        self.dealer_cards = []
        self.player_cards = []
        
        self.gui_queue = queue.Queue()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.root.withdraw()
        self.team_name = simpledialog.askstring("Login", "Enter your Team Name:", parent=self.root)
        if not self.team_name:
            self.team_name = "Guest"
        self.root.deiconify()

        self.setup_ui()
        self.check_gui_queue()
        
        print("Client started, listening for offer requests...")
        
        self.network_thread = threading.Thread(target=self.udp_listener_loop, daemon=True)
        self.network_thread.start()

    def setup_ui(self):
        header_frame = tk.Frame(self.root, bg='#0d4d0d', pady=20)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="♠ ♥ BLACKJACK ♦ ♣", font=('Arial', 28, 'bold'), bg='#0d4d0d', fg='gold').pack()
        self.team_lbl = tk.Label(header_frame, text=f"Team: {self.team_name}", font=('Arial', 14), bg='#0d4d0d', fg='white')
        self.team_lbl.pack()

        table_frame = tk.Frame(self.root, bg='#0d6d0d', relief=tk.RAISED, borderwidth=3)
        table_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        dealer_frame = tk.Frame(table_frame, bg='#0d6d0d', pady=10)
        dealer_frame.pack(fill=tk.X)
        tk.Label(dealer_frame, text="🎩 DEALER", font=('Arial', 16, 'bold'), bg='#0d6d0d', fg='white').pack()
        self.dealer_value_label = tk.Label(dealer_frame, text="Value: --", font=('Arial', 12), bg='#0d6d0d', fg='yellow')
        self.dealer_value_label.pack()
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#0d6d0d', height=120)
        self.dealer_cards_frame.pack(pady=10, fill=tk.X)

        tk.Frame(table_frame, bg='gold', height=2).pack(fill=tk.X, padx=50, pady=10)

        player_frame = tk.Frame(table_frame, bg='#0d6d0d', pady=10)
        player_frame.pack(fill=tk.X)
        tk.Label(player_frame, text="👤 YOU", font=('Arial', 16, 'bold'), bg='#0d6d0d', fg='white').pack()
        self.player_value_label = tk.Label(player_frame, text="Value: --", font=('Arial', 12), bg='#0d6d0d', fg='yellow')
        self.player_value_label.pack()
        self.player_cards_frame = tk.Frame(player_frame, bg='#0d6d0d', height=120)
        self.player_cards_frame.pack(pady=10, fill=tk.X)

        self.status_lbl = tk.Label(self.root, text="🔍 Looking for server...", font=('Arial', 12, 'bold'), bg='#0d4d0d', fg='cyan')
        self.status_lbl.pack(pady=5)

        btn_frame = tk.Frame(self.root, bg='#0d4d0d', pady=10)
        btn_frame.pack()
        self.btn_hit = tk.Button(btn_frame, text="🎯 HIT", command=lambda: self.set_action("Hit"), width=12, height=2, font=('Arial', 14, 'bold'), bg='#28a745', fg='white', state=tk.DISABLED)
        self.btn_hit.pack(side=tk.LEFT, padx=15)
        self.btn_stand = tk.Button(btn_frame, text="✋ STAND", command=lambda: self.set_action("Stand"), width=12, height=2, font=('Arial', 14, 'bold'), bg='#dc3545', fg='white', state=tk.DISABLED)
        self.btn_stand.pack(side=tk.LEFT, padx=15)

        tk.Button(self.root, text="🚪 QUIT", command=self.on_closing, bg='gray', fg='white').pack(side=tk.BOTTOM, pady=10)

    # --- Net Utils ---
    def check_gui_queue(self):
        while not self.gui_queue.empty():
            func, args = self.gui_queue.get()
            try: func(*args)
            except Exception as e: print(f"GUI Error: {e}")
        if self.running: self.root.after(50, self.check_gui_queue)

    def run_on_main(self, func, *args):
        self.gui_queue.put((func, args))

    def safe_recv(self, sock, size):
        data = b''
        while len(data) < size and self.running:
            try:
                chunk = sock.recv(size - len(data))
                if not chunk: return None
                data += chunk
            except socket.timeout: continue
            except OSError: return None
            except Exception as e: return None
        return data

    def udp_listener_loop(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except: udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp.bind(('', UDP_PORT))
        udp.settimeout(1.0)
        while self.running:
            try:
                data, addr = udp.recvfrom(1024)
                
                print(f"Received offer from {addr[0]}")
                
                if self.is_playing: continue
                offer = protocol.unpack_offer(data)
                if offer:
                    port, name = offer
                    self.run_on_main(self.show_rounds_dialog, name, addr[0], port)
                    time.sleep(5) 
            except: pass

    def show_rounds_dialog(self, name, ip, port):
        if self.is_playing or self.in_dialog: return
        
        self.in_dialog = True  # נועלים
        try:
            rounds = simpledialog.askinteger("Server Found", f"Connected to '{name}'\nHow many rounds?", parent=self.root, minvalue=1, maxvalue=10)
            
            if rounds:
                self.is_playing = True
                threading.Thread(target=self.game_session, args=(ip, port, rounds), daemon=True).start()
        finally:
            self.in_dialog = False 

    def game_session(self, ip, port, rounds):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(None)
            self.tcp_socket.connect((ip, port))
            self.tcp_socket.send(protocol.pack_request(rounds, self.team_name))

            wins = 0
            for i in range(rounds):
                if not self.running: break
                
                self.update_status(f"Round {i+1} of {rounds} - Starting...", "yellow")
                self.run_on_main(self.clear_board)
                self.dealer_cards = []
                self.player_cards = []
                
                try:
                    result = self.play_round()
                    if result == "ERROR": 
                        print(f"[ROUND {i+1}] Error. Recovering...")
                    elif result == 1: 
                        wins += 1
                except Exception as e:
                    print(f"[CRITICAL ERR] {e}")
                    break
                
                if i < rounds - 1:
                    time.sleep(3) 
            win_rate = wins / rounds if rounds > 0 else 0.0        
            print(f"Finished playing {rounds} rounds, win rate: {win_rate}")
            if self.running:
                self.run_on_main(messagebox.showinfo, "Game Over", f"Finished!\nTotal Wins: {wins}/{rounds}")
        
        except Exception as e:
            print(f"Session Error: {e}")
        finally:
            self.close_socket()
            self.is_playing = False
            self.update_status("Looking for server...", "cyan")

    def play_round(self):
        print("\n--- NEW ROUND STARTED ---")
        
        # --- SRT Sync ---
        print("[ROUND] Searching for SRT...")
        buffer = b""
        while self.running:
            byte = self.safe_recv(self.tcp_socket, 1)
            if not byte: return "ERROR"
            buffer += byte
            if b"SRT" in buffer: break
            if len(buffer) > 100: buffer = buffer[-3:] 

        print("[ROUND] SRT Found! Reading cards...")
        
        # 1. קבלת קלפים
        for i in range(3):
            data = self.safe_recv(self.tcp_socket, MSG_SIZE)
            if not data: return "ERROR"
            parsed = protocol.unpack_server_message(data)
            if not parsed: return "ERROR"
            res, r, s = parsed
            self.add_card_gui(r, s, is_dealer=(i==2))

        try: self.tcp_socket.send(b"RDY")
        except: return "ERROR"
        
        go_signal = self.safe_recv(self.tcp_socket, 3) 
        if not go_signal or b"GO" not in go_signal: return "ERROR"
        
        print("[ROUND] GO received!")

        # 2. משחק
        while self.running:
            self.enable_buttons(True)
            self.update_status("YOUR TURN: Hit or Stand?", "lime")
            self.action_event.clear()
            self.action_event.wait()
            if not self.running: return "ERROR"
            
            action = self.user_action
            self.enable_buttons(False)
            
            try: self.tcp_socket.send(protocol.pack_client_decision(action))
            except: return "ERROR"
            
            if action == "Stand": break 
            
            data = self.safe_recv(self.tcp_socket, MSG_SIZE)
            if not data: return "ERROR"
            parsed = protocol.unpack_server_message(data)
            if not parsed: return "ERROR"
            res, r, s = parsed
            self.add_card_gui(r, s, is_dealer=False)
            if res != 0: break 

        # 3. תוצאות
        self.update_status("Round Over. Results...", "orange")
        while self.running:
            data = self.safe_recv(self.tcp_socket, MSG_SIZE)
            if not data: return "ERROR"
            
            parsed = protocol.unpack_server_message(data)
            if not parsed: return "ERROR"
            res, r, s = parsed
            
            # --- התיקון לכפילות ---
            skip = False
            # אם יש לנו כבר קלפים אצל הדילר, והקלף החדש זהה לקלף *האחרון* שקיבלנו - זה שכפול!
            if self.dealer_cards and self.dealer_cards[-1] == (r,s):
                skip = True
            
            if not skip:
                self.add_card_gui(r, s, is_dealer=True)
            
            if res != 0:
                final_text = "WIN! 🏆" if res == 3 else "LOSE 💀" if res == 2 else "TIE 🤝"
                self.update_status(final_text, "gold" if res==3 else "red")
                print(f"[ROUND] Result: {res}")
                return 1 if res == 3 else 0
        return "ERROR"

    # Helpers
    def set_action(self, action):
        self.user_action = action
        self.action_event.set()

    def add_card_gui(self, r, s, is_dealer):
        self.run_on_main(self._draw_card, r, s, is_dealer)

    def _draw_card(self, rank, suit, is_dealer):
        lst = self.dealer_cards if is_dealer else self.player_cards
        lst.append((rank, suit))
        frame = self.dealer_cards_frame if is_dealer else self.player_cards_frame
        
        card_cont = tk.Frame(frame, bg='#0d6d0d')
        card_cont.pack(side=tk.LEFT, padx=5)
        cv = tk.Canvas(card_cont, bg='white', width=70, height=100, relief=tk.RAISED, bd=2)
        cv.pack()
        
        color = 'red' if suit in [1, 2] else 'black'
        rn = {1:'A', 11:'J', 12:'Q', 13:'K'}
        ss = {0:'♠', 1:'♥', 2:'♦', 3:'♣'}
        rt = rn.get(rank, str(rank))
        st = ss.get(suit, '?')
        
        cv.create_text(10, 10, text=rt, fill=color, font=('Arial', 14, 'bold'), anchor='nw')
        cv.create_text(35, 50, text=st, fill=color, font=('Arial', 32), anchor='center')
        cv.create_text(60, 90, text=rt, fill=color, font=('Arial', 14, 'bold'), anchor='se')
        
        val = self.calc_val(lst)
        lbl = self.dealer_value_label if is_dealer else self.player_value_label
        lbl.config(text=f"Value: {val}")

    def calc_val(self, cards):
        v, a = 0, 0
        for r, s in cards:
            if r==1: a+=1; v+=11
            elif r>10: v+=10
            else: v+=r
        while v>21 and a>0: v-=10; a-=1
        return v

    def clear_board(self):
        for w in self.dealer_cards_frame.winfo_children(): w.destroy()
        for w in self.player_cards_frame.winfo_children(): w.destroy()
        self.dealer_value_label.config(text="Value: --")
        self.player_value_label.config(text="Value: --")

    def update_status(self, txt, col):
        self.run_on_main(lambda: self.status_lbl.config(text=txt, fg=col))

    def enable_buttons(self, state):
        s = tk.NORMAL if state else tk.DISABLED
        self.run_on_main(lambda: (self.btn_hit.config(state=s), self.btn_stand.config(state=s)))

    def close_socket(self):
        try:
            if self.tcp_socket: self.tcp_socket.close()
        except: pass

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to exit?"):
            self.running = False
            self.action_event.set()
            self.close_socket()
            self.root.destroy()
            sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = BlackjackClientGUI(root)
    root.mainloop()