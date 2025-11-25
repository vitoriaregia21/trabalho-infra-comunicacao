# Cliente.py
import socket
import threading
import hashlib
import random
import time

HOST = "127.0.0.1"
PORT = 5001

def calcular_checksum_manual(dados: str) -> str:
    soma = 0
    for i, c in enumerate(dados):
        soma += (i + 1) * ord(c)  
    return hex(soma)[2:].zfill(8)[:8]

def enviar_pacote(seq: int, carga: str):
    global modo_erro
    if client_socket.fileno() == -1:
        print(f"[CLIENT] Tentativa de envio ignorada — socket já foi fechado.")
        return
    
    if modo_erro in ["2", "3"]:
        delay = random.uniform(0, 2)
        time.sleep(delay)

    checksum = calcular_checksum_manual(carga)

    if modo_erro == "2" and random.random() < 0.4:
        print(f"[CLIENT] Pacote {seq:02d} perdido!")
        return

    payload = carga
    if modo_erro == "3" and random.random() < 0.4:
        payload = "X" * len(carga)
        print(f"[CLIENT] Pacote {seq:02d} corrompido! (enviado '{payload}')")

    frame = f"{seq:02d} - S - {payload} - {checksum}"

    try:
        client_socket.sendall(frame.encode())
        print(f"[CLIENT] Enviado: {frame}")
    except OSError:
        print(f"[CLIENT] Erro: não foi possível enviar o pacote {seq:02d} — socket fechado.")
        return

    if modo_erro in ["2", "3"] and random.random() < 0.2:
        tipo = random.choice(["duplicado", "fora_ordem"])
        time.sleep(0.1)

        if tipo == "duplicado":
            try:
                client_socket.sendall(frame.encode())
                print(f"[CLIENT] Enviado duplicado: {frame}")
            except OSError:
                print(f"[CLIENT] Erro ao duplicar o pacote {seq:02d} — socket fechado.")
        elif tipo == "fora_ordem" and seq > 1:
            frame_prev = f"{seq-1:02d} - S - {frames[seq-2]} - {calcular_checksum_manual(frames[seq-2])}"
            try:
                client_socket.sendall(frame_prev.encode())
                print(f"[CLIENT] Enviado fora de ordem: {frame_prev}")
            except OSError:
                print(f"[CLIENT] Erro ao enviar fora de ordem — socket fechado.")

def ack_listener():
    global send_base
    while True:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
            resp = data.decode()
        except ConnectionResetError:
            break

        if resp == "FIM_ACK":
            break

        if resp.startswith("ACK"):
            num = int(resp[3:5])
            print(f"[CLIENT] Recebeu ACK {num:02d}")
            if protocolo == "1":            
                if num >= send_base:
                    send_base = num + 1
                    timers['gbn'].cancel()
                    if send_base < next_seq:
                        if 'gbn' in timers:
                            timers['gbn'].cancel()
                        timers['gbn'] = threading.Timer(timeout, timeout_gbn)
                        timers['gbn'].start()
            elif protocolo == "2":
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
                break

        elif resp.startswith("NAK"):
            num = int(resp[3:5])
            print(f"[CLIENT] Recebeu NAK {num:02d}")
            if protocolo == "1":
                timers['gbn'].cancel()
                timeout_gbn()
            else:
                enviar_pacote(num, frames[num-1])
                timers[num].cancel()
                t = threading.Timer(timeout, lambda idx=num: timeout_sr(idx))
                timers[num] = t; t.start()

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
    protocolo = input("Protocolo:\n1=Go‑Back‑N\n2=Repetição Seletiva\n-> ")
    if protocolo in ["1", "2"]:
        break
    print("Valor inválido! Digite 1 ou 2.")

while True:
    modo_erro = input("Modo:\n1=Seguro\n2=Com perda\n3=Com erro\n-> ")
    if modo_erro in ["1", "2", "3"]:
        break
    print("Valor inválido! Digite 1, 2 ou 3.")
    
packet_size = 3
window_size = int(input("Tamanho da janela: "))
timeout     = float(input("Timeout (segundos): "))
mensagem    = input("Mensagem a enviar: ")

client_socket.sendall(f"{protocolo},{modo_erro},{packet_size},{window_size}".encode())
resp = client_socket.recv(1024).decode()
print(f"[CLIENT] Handshake: {resp}")

frames     = [mensagem[i:i+packet_size] for i in range(0, len(mensagem), packet_size)]
n_frames   = len(frames)
send_base  = 1
next_seq   = 1
acked      = set()
timers     = {}

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
    while next_seq <= n_frames:
        enviar_pacote(next_seq, frames[next_seq-1])
        t = threading.Timer(timeout, lambda idx=next_seq: timeout_sr(idx))
        timers[next_seq] = t; t.start()
        next_seq += 1

    max_wait = time.time() + timeout * 20
    while len(acked) < n_frames:
        faltando = [i for i in range(1, n_frames+1) if i not in acked]
        print(f"[CLIENT] Aguardando ACKs: {faltando}")
        if time.time() > max_wait:
            print("[CLIENT] Tempo máximo de espera excedido. Encerrando.")
            break
        time.sleep(0.5)

client_socket.sendall("FIM".encode())

listener.join()

for t in timers.values():
    t.cancel()

client_socket.close()
print("[CLIENT] Conexão encerrada")