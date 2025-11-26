import socket
import hashlib

HOST = "127.0.0.1"
PORT = 5001

MODOS_ERRO = {"1": "Seguro", "2": "Com Perda", "3": "Com Erro"}
CRYPTO_KEY = "segredo123"

def calcular_checksum_manual(dados: str) -> str:
    soma = 0
    for i, c in enumerate(dados):
        soma += (i + 1) * ord(c)
    return hex(soma)[2:].zfill(8)[:8]

def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def decrypt_text(cipher_hex: str) -> str:
    data = bytes.fromhex(cipher_hex)
    key_bytes = CRYPTO_KEY.encode("utf-8")
    plain = xor_bytes(data, key_bytes)
    return plain.decode("utf-8")

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"[SERVER] Aguardando conexões em {HOST}:{PORT}...")

conn, addr = server_socket.accept()
print(f"[SERVER] Conectado por {addr}")

try:
    hs = conn.recv(1024).decode().split(",")
    protocolo   = hs[0]
    modo_erro   = hs[1]
    chunk_size  = int(hs[2])
    crypto_flag = hs[3]
    use_crypto  = (crypto_flag == "1")

    # janela agora é definida somente pelo servidor
    window_size = 4

    tipo = 'GBN' if protocolo=='1' else 'SR'
    print(f"[SERVER] Protocolo={tipo}, Modo={MODOS_ERRO[modo_erro]}, PacketMax={chunk_size}, Janela={window_size}")

    # envia também o tamanho da janela para o cliente
    conn.sendall(f"HANDSHAKE_OK:{tipo}:{window_size}".encode())

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
            try:
                seq = int(data[:2])
                conn.sendall(f"NAK{seq:02d}".encode())
            except:
                conn.sendall("NAK00".encode())  
            continue

        seq_str, flag, carga, chk = partes
        seq = int(seq_str)

        # descriptografa se necessário
        try:
            if use_crypto:
                texto_claro = decrypt_text(carga)
            else:
                texto_claro = carga
        except Exception:
            print(f"[SERVER] Erro ao decifrar pacote {seq:02d}, enviando NAK")
            conn.sendall(f"NAK{seq:02d}".encode())
            continue

        if chk != calcular_checksum_manual(texto_claro) or len(texto_claro) > chunk_size:
            print(f"[SERVER] Erro no pacote {seq:02d}, enviando NAK")
            if protocolo == "1":
                conn.sendall(f"NAK{seq:02d}".encode())
            elif protocolo == "2":
                conn.sendall(f"NAK{seq:02d}".encode())
            continue

        print(f"[SERVER] Recebido pacote {seq:02d}: '{texto_claro}'")

        if protocolo == "1":
            if seq == expected:
                frames_recv[seq] = texto_claro
                conn.sendall(f"ACK{seq:02d}".encode())
                expected += 1
            else:
                conn.sendall(f"ACK{expected-1:02d}".encode())

        elif protocolo == "2":
            if recv_base <= seq < recv_base + window_size and seq not in buffer_sr:
                buffer_sr[seq] = texto_claro
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
