import socket
import hashlib

HOST = "127.0.0.1"
PORT = 5001

MODOS_ERRO = {"1": "Seguro", "2": "Com Perda", "3": "Com Erro"}

def calcular_checksum_manual(dados: str) -> str:
    soma = 0
    for i, c in enumerate(dados):
        soma += (i + 1) * ord(c)
    return hex(soma)[2:].zfill(8)[:8]

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"[SERVER] Aguardando conexões em {HOST}:{PORT}...")

conn, addr = server_socket.accept()
print(f"[SERVER] Conectado por {addr}")

try:
    hs = conn.recv(1024).decode().split(",")
    protocolo, modo_erro, chunk_size, window_size = hs[0], hs[1], int(hs[2]), int(hs[3])
    tipo = 'GBN' if protocolo=='1' else 'SR'
    print(f"[SERVER] Protocolo={tipo}, Modo={MODOS_ERRO[modo_erro]}, PacketMax={chunk_size}, Janela={window_size}")
    conn.sendall(f"HANDSHAKE_OK:{tipo}".encode())

    frames_recv = {}
    if protocolo == "1":
        expected = 1
    else:
        recv_base = 1
        buffer_sr = {}

    while True:
        data = conn.recv(1024).decode()
        if not data:
            continue

        if data == "FIM":
            conn.sendall("FIM_ACK".encode())
            break

        partes = data.split(" - ")
        if len(partes) != 4:
            print(f"[SERVER] Frame inválido: {data}")
            continue

        seq, flag, carga, chk = int(partes[0]), partes[1], partes[2], partes[3]
        if chk != calcular_checksum_manual(carga) or len(carga) > chunk_size:
            print(f"[SERVER] Erro no pacote {seq:02d}, enviando NAK")
            conn.sendall(f"NAK{seq:02d}".encode())
            continue

        print(f"[SERVER] Recebido pacote {seq:02d}: '{carga}'")

        if protocolo == "1":
            if seq == expected:
                frames_recv[seq] = carga
                conn.sendall(f"ACK{seq:02d}".encode())
                expected += 1
            else:
                conn.sendall(f"ACK{expected-1:02d}".encode())
        elif protocolo == "2":
            if recv_base <= seq < recv_base + window_size and seq not in buffer_sr:
                buffer_sr[seq] = carga
                conn.sendall(f"ACK{seq:02d}".encode())
                if seq == recv_base:
                    while recv_base in buffer_sr:
                        frames_recv[recv_base] = buffer_sr.pop(recv_base)
                        recv_base += 1
            else:
                conn.sendall(f"ACK{seq:02d}".encode())

    final = "".join(frames_recv[i] for i in sorted(frames_recv))
    print(f"[SERVER] Mensagem reconstruída: {final}")

finally:
    conn.close()
    server_socket.close()
    print("[SERVER] Conexão encerrada")