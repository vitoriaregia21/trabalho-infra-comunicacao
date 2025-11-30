import socket
import threading
import hashlib
import time

HOST = "127.0.0.1"
PORT = 5001

CRYPTO_KEY = "segredo123"

def calcular_checksum_manual(dados: str) -> str:
    soma = 0
    for i, c in enumerate(dados):
        soma += (i + 1) * ord(c)  
    return hex(soma)[2:].zfill(8)[:8]

def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def encrypt_text(plaintext: str) -> str:
    data = plaintext.encode("utf-8")
    key_bytes = CRYPTO_KEY.encode("utf-8")
    cipher = xor_bytes(data, key_bytes)

    return cipher.hex()

pacotes_perda_uma_vez = set()
pacotes_erro_uma_vez = set()
use_crypto = False

def enviar_pacote(seq: int, carga: str):
    global modo_erro, use_crypto
    if client_socket.fileno() == -1:
        print(f"[CLIENT] Tentativa de envio ignorada — socket já foi fechado.")
        return

    texto_claro = carga
    checksum = calcular_checksum_manual(texto_claro)

    payload = texto_claro
    if use_crypto:
        payload = encrypt_text(texto_claro)

    if modo_erro == "2" and seq in pacotes_perda_uma_vez:
        print(f"[CLIENT] Pacote {seq:02d} perdido!")
        pacotes_perda_uma_vez.remove(seq)
        return

    if modo_erro == "3" and seq in pacotes_erro_uma_vez:
        if use_crypto:
    
            payload = "0" * len(payload)
        else:
            payload = "X" * len(texto_claro)
        print(f"[CLIENT] Pacote {seq:02d} corrompido! (enviado '{payload}')")
        pacotes_erro_uma_vez.remove(seq)

    frame = f"{seq:02d} - S - {payload} - {checksum}"

    try:
        client_socket.sendall(frame.encode())
        print(f"[CLIENT] Enviado: {frame}")
    except OSError:
        print(f"[CLIENT] Erro: não foi possível enviar o pacote {seq:02d} — socket fechado.")
        return

def ack_listener():
    global send_base
    buffer = ""
    fim = False

    while not fim:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
            buffer += data.decode()
        except ConnectionResetError:
            break

        # Processa TODAS as mensagens completas que estiverem no buffer
        while True:
            if buffer.startswith("FIM_ACK"):
                fim = True
                buffer = buffer[7:]  # remove "FIM_ACK"
                break

            elif buffer.startswith("ACK") and len(buffer) >= 5:
                msg = buffer[:5]
                buffer = buffer[5:]
                num = int(msg[3:5])
                print(f"[CLIENT] Recebeu ACK {num:02d}")

                if protocolo == "1":  # GBN
                    if num >= send_base:
                        send_base = num + 1
                        if 'gbn' in timers:
                            timers['gbn'].cancel()
                        if send_base < next_seq:
                            timers['gbn'] = threading.Timer(timeout, timeout_gbn)
                            timers['gbn'].start()

                elif protocolo == "2":  # SR
                    if num not in acked:
                        acked.add(num)
                        if num in timers:
                            timers[num].cancel()
                            del timers[num]
                    if num == send_base:
                        while send_base in acked:
                            send_base += 1

                else:
                    print(f"[CLIENT] Escolha inválida: {protocolo}")
                    fim = True
                    break

            elif buffer.startswith("NAK") and len(buffer) >= 5:
                msg = buffer[:5]
                buffer = buffer[5:]
                num = int(msg[3:5])
                print(f"[CLIENT] Recebeu NAK {num:02d}")

                if protocolo == "1":  # GBN
                    if 'gbn' in timers:
                        timers['gbn'].cancel()
                    timeout_gbn()
                else:  # SR
                    enviar_pacote(num, frames[num-1])
                    if num in timers:
                        timers[num].cancel()
                    t = threading.Timer(timeout, lambda idx=num: timeout_sr(idx))
                    timers[num] = t
                    t.start()

            else:
                # Se não tem mensagem completa, espera mais dados
                if len(buffer) < 5:
                    break
                # descarta 1 caractere "lixo" e tenta de novo
                buffer = buffer[1:]

    print("[CLIENT] Listener encerrado")

def timeout_gbn():
    global send_base
    if send_base > n_frames:
        return  
    print(f"[CLIENT] Timeout GBN, retransmitindo a partir de {send_base:02d}")
    for i in range(send_base, min(send_base + window_size, n_frames + 1)):
        enviar_pacote(i, frames[i-1])
    t = threading.Timer(timeout, timeout_gbn)
    timers['gbn'] = t; t.start()

def timeout_sr(idx: int):
    if idx in acked:
        return 
    print(f"[CLIENT] Timeout SR para pacote {idx:02d}, retransmitindo")
    enviar_pacote(idx, frames[idx-1])
    if idx in timers:
        timers[idx].cancel()
    timers[idx] = threading.Timer(timeout, lambda: timeout_sr(idx))
    timers[idx].start()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))

while True:
    protocolo = input("Protocolo:\n1=Go-Back-N\n2=Repetição Seletiva\n-> ")
    if protocolo in ["1", "2"]:
        break
    print("Valor inválido! Digite 1 ou 2.")

while True:
    modo_erro = input("Modo:\n1=Seguro\n2=Com perda\n3=Com erro\n-> ")
    if modo_erro in ["1", "2", "3"]:
        break
    print("Valor inválido! Digite 1, 2 ou 3.")

resp_crypto = input("Ativar criptografia simétrica? (s/n): ").strip().lower()
use_crypto = (resp_crypto == "s")
    
packet_size = 3
timeout     = float(input("Timeout (segundos): "))

while True:
    mensagem = input("Mensagem a enviar (mínimo 30 caracteres): ")
    if len(mensagem) >= 30:
        break
    print(f"Mensagem muito curta ({len(mensagem)} caracteres). Digite pelo menos 30.")

crypto_flag = "1" if use_crypto else "0"
client_socket.sendall(f"{protocolo},{modo_erro},{packet_size},{crypto_flag}".encode())
resp = client_socket.recv(1024).decode()
print(f"[CLIENT] Handshake: {resp}")


window_size = 5  # valor padrão caso o handshake venha errado

if resp.startswith("HANDSHAKE_OK:"):
    partes = resp.split(":")
    if len(partes) >= 3:
        tipo = partes[1]
        try:
            w = int(partes[2])
            if 1 <= w <= 5:
                window_size = w
            else:
                print(f"[CLIENT] Janela inválida recebida ({w}), usando 5.")
        except ValueError:
            print("[CLIENT] Erro ao ler tamanho da janela, usando 5.")
else:
    print("[CLIENT] Handshake inesperado, usando janela 5.")

print(f"[CLIENT] Janela configurada = {window_size}")

frames     = [mensagem[i:i+packet_size] for i in range(0, len(mensagem), packet_size)]
n_frames   = len(frames)
send_base  = 1
next_seq   = 1
acked      = set()
timers     = {}

if modo_erro == "2":
    entrada = input(f"Informe os números de sequência dos pacotes a serem PERDIDOS (1–{n_frames}), separados por vírgula (ou deixe vazio): ")
    if entrada.strip():
        for v in entrada.split(","):
            v = v.strip()
            if v.isdigit():
                idx = int(v)
                if 1 <= idx <= n_frames:
                    pacotes_perda_uma_vez.add(idx)

elif modo_erro == "3":
    entrada = input(f"Informe os números de sequência dos pacotes a serem CORROMPIDOS (1–{n_frames}), separados por vírgula (ou deixe vazio): ")
    if entrada.strip():
        for v in entrada.split(","):
            v = v.strip()
            if v.isdigit():
                idx = int(v)
                if 1 <= idx <= n_frames:
                    pacotes_erro_uma_vez.add(idx)

listener = threading.Thread(target=ack_listener)
listener.start()

if protocolo == "1":
    timers['gbn'] = threading.Timer(timeout, timeout_gbn)
    timers['gbn'].start()
    while send_base <= n_frames:
        while next_seq < send_base + window_size and next_seq <= n_frames:
            enviar_pacote(next_seq, frames[next_seq-1])
            next_seq += 1
        time.sleep(0.1)
else:
    max_wait = time.time() + timeout * 20

    while len(acked) < n_frames and time.time() <= max_wait:
        # preenche a janela enquanto houver espaço
        while next_seq <= n_frames and next_seq <= send_base + window_size - 1:
            enviar_pacote(next_seq, frames[next_seq-1])
            if next_seq not in timers:
                t = threading.Timer(timeout, lambda idx=next_seq: timeout_sr(idx))
                timers[next_seq] = t
                t.start()
            next_seq += 1

        faltando = [i for i in range(1, n_frames+1) if i not in acked]
        print(f"[CLIENT] Aguardando ACKs (SR): {faltando}")
        time.sleep(0.2)

    if len(acked) < n_frames:
        print("[CLIENT] Tempo máximo de espera excedido. Encerrando.")

client_socket.sendall("FIM".encode())

listener.join()

for t in timers.values():
    t.cancel()

client_socket.close()
print("[CLIENT] Conexão encerrada")
