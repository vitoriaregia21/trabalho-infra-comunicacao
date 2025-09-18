import socket

def cliente():
    host = "127.0.0.1"
    port = 9090
    tam_max = 50 

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    s.send(f"SYN|{tam_max}".encode())

    resposta = s.recv(1024).decode().strip()
    if resposta.startswith("SYN-ACK|"):
        print(f"[CLIENTE] Recebeu: {resposta}")
        s.send("ACK".encode())
        print("[CLIENTE] Handshake concluído com sucesso!")
    else:
        print("[CLIENTE] Resposta inválida do servidor.")

    s.close()

if __name__ == "__main__":
    cliente()
