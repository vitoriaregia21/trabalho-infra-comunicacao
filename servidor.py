import socket

def servidor():
    host = "127.0.0.1"
    port = 9090

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((host, port))
        print(f"[SERVIDOR] Servidor vinculado em {host}:{port}")
    except socket.error as e:
        print(f"[SERVIDOR] Erro ao vincular o servidor: {e}")
        return
    
    server_socket.listen(5)
    print("[SERVIDOR] Servidor escutando por conexões...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"[SERVIDOR] Conexão aceita de {addr}")

        try:
            data = client_socket.recv(1024).decode().strip()
            print(f"[SERVIDOR] Recebeu do cliente: '{data}'")

            if data.startswith("SYN|"):
                parts = data.split('|')
                if len(parts) == 2:
                    mode_proposto = parts[0]
                    tam_max_cliente = int(parts[1])

                    print(f"[SERVIDOR] Handshake - Modo proposto: '{mode_proposto}', Tamanho Máximo do Cliente: {tam_max_cliente}")

                    server_response = f"SYN-ACK|MODE_TEXT|{tam_max_cliente}"
                    client_socket.send(server_response.encode())
                    print(f"[SERVIDOR] Enviou para o cliente: '{server_response}'")

                    final_ack = client_socket.recv(1024).decode().strip()
                    if final_ack == "ACK":
                        print("[SERVIDOR] Recebeu ACK final do cliente. Handshake concluído com sucesso!")
    
                    else:
                        print(f"[SERVIDOR] Recebeu resposta inesperada após SYN-ACK: '{final_ack}'. Handshake falhou.")
                else:
                    print("[SERVIDOR] Formato SYN inválido recebido.")
                    client_socket.send("NACK|INVALID_SYN_FORMAT".encode())
            else:
                print("[SERVIDOR] Mensagem inicial não é SYN. Handshake falhou.")
                client_socket.send("NACK|NOT_SYN".encode()) 

        except Exception as e:
            print(f"[SERVIDOR] Erro durante a comunicação com o cliente {addr}: {e}")
        finally:
            client_socket.close()
            print(f"[SERVIDOR] Conexão com {addr} fechada.")

if __name__ == "__main__":
    servidor()