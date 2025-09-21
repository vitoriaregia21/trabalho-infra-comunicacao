import socket

def cliente():
    host = "127.0.0.1"
    port = 9090
    tam_max = 50 

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        print(f"[CLIENTE] Conectado ao servidor em {host}:{port}")

        s.send(f"SYN|{tam_max}".encode())
        print(f"[CLIENTE] Enviou: SYN|{tam_max}")

        resposta = s.recv(1024).decode().strip()
        print(f"[CLIENTE] Recebeu: {resposta}")

        if resposta.startswith("SYN-ACK|"):
            s.send("ACK".encode())
            print("[CLIENTE] Enviou: ACK")
            print("[CLIENTE] Handshake concluído com sucesso!")
        else:
            print(f"[CLIENTE] Resposta inválida do servidor: {resposta}")

    except ConnectionRefusedError:
        print(f"[CLIENTE ERRO] O servidor pode não estar ativo ou não está escutando na porta {port}.")
    except Exception as e:
        print(f"[CLIENTE ERRO] Ocorreu um erro: {e}")
    finally:
        s.close()
        print("[CLIENTE] Conexão fechada.")

if __name__ == "__main__":
    cliente()