import socket

def servidor():
    host = "127.0.0.1"
    port = 9090

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen(1)
    print(f"[SERVIDOR] Aguardando conexão em {host}:{port}...")

    client_socket, endereco = s.accept()
    print(f"[SERVIDOR] Cliente conectado: {endereco}")

    dados = client_socket.recv(1024).decode().strip()
    print(f"[SERVIDOR] Recebeu: {dados}")

    if dados.startswith("SYN|"):
        tam_max = dados.split("|")[1]
        client_socket.send(f"SYN-ACK|{tam_max}".encode())
        print(f"[SERVIDOR] Enviou: SYN-ACK")
        ack = client_socket.recv(1024).decode().strip()
        if ack == "ACK":
            print("[SERVIDOR] Handshake concluído com sucesso!")
        else:
            print("[SERVIDOR] ACK inválido recebido.")
    else:
        print("[SERVIDOR] Formato de SYN inválido.")

    client_socket.close()
    s.close()

if __name__ == "__main__":
    servidor()
