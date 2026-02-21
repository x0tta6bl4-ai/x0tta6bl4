import sys
import logging
import threading
import time

# Add project root to path to import libx0t
sys.path.append(".")

import libx0t

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def start_server():
    import socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9001))
    server.listen(1)
    print("Server listening on 9001...")
    
    conn, addr = server.accept()
    print(f"Connection from {addr}")
    
    # Simple Mock Server Logic to handle Handshake
    msg = conn.recv(1024) # CLIENT_HELLO
    print(f"Server received: {msg}")
    
    conn.sendall(b"MOCK_SERVER_PUBLIC_KEY")
    
    ciphertext = conn.recv(1024)
    print(f"Server received ciphertext: {ciphertext}")
    
    # Chat loop
    while True:
        data = conn.recv(1024)
        if not data: break
        print(f"Server received msg: {data}")
        conn.sendall(b"Server ACK: " + data)
        
def start_client():
    node = libx0t.Node()
    time.sleep(1) # Wait for server
    
    try:
        tunnel = node.connect("127.0.0.1:9001", secure=True)
        
        tunnel.send(b"Hello Quantum World!")
        response = tunnel.receive()
        print(f"Client received: {response}")
        
        tunnel.close()
    except Exception as e:
        print(f"Client error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        start_server()
    else:
        # Run both in threads for demo
        t_server = threading.Thread(target=start_server)
        t_server.daemon = True
        t_server.start()
        
        start_client()
        time.sleep(2)
