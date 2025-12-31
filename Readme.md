# 🃏 Multiplayer Network Blackjack

A robust, multi-threaded implementation of a distributed Blackjack game using Python.
This project features a **Graphic User Interface (GUI)**, dynamic network discovery, and advanced synchronization mechanisms to support multiple players simultaneously.

## ✨ Key Features
* **Graphic UI:** A polished Tkinter-based interface with animations and visual feedback.
* **Auto-Discovery:** Clients automatically find the server using UDP Broadcasts (no hardcoded IPs!).
* **Multiplayer Synchronization:** Uses `Threading.Barrier` to ensure all players see game events (dealing, revealing) simultaneously.
* **Robust Networking:**
    * Handles packet fragmentation and corruption.
    * Implements `Watchdog` timers to prevent deadlocks.
    * Supports dynamic TCP port allocation.
    * **No Busy Waiting:** Efficient use of Blocking I/O and Event objects (0% CPU idle usage).
* **Cross-Platform:** Supports running multiple clients on the same machine using `SO_REUSEPORT`/`SO_REUSEADDR`.

---

## 🚀 How to Run

### Prerequisites
* Python 3.6 or higher.
* Standard libraries only (tkinter, socket, threading, struct).

### 1. Start the Server
The server listens on a dynamic TCP port and broadcasts offers via UDP (Port 13122).
```bash
python server.py