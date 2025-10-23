import socket

# ---------- Protocolo / utilitários ----------
PAYLOAD_SIZE = 4   # máximo 4 caracteres por pacote
PKT_LEN = 4 + 4 + 4 + 3  # data(4) + seq(4) + lastseq(4) + checksum(3) = 15

def checksum_for(data_str):
    # soma bytes e modulo 256
    return sum(bytearray(data_str.encode())) % 256

def make_pkt(data, seqnum, lastseq):
    data_fixed = data.ljust(PAYLOAD_SIZE)[:PAYLOAD_SIZE]
    seq_s = f"{seqnum:04d}"
    last_s = f"{lastseq:04d}"
    ch = checksum_for(data_fixed + seq_s + last_s) % 256
    ch_s = f"{ch:03d}"
    return f"{data_fixed}{seq_s}{last_s}{ch_s}"

def parse_pkt(pkt_str):
    if len(pkt_str) != PKT_LEN:
        raise ValueError("[PARSE ERROR] length mismatch")
    data = pkt_str[0:PAYLOAD_SIZE]
    seqnum = int(pkt_str[4:8])
    lastseq = int(pkt_str[8:12])
    rcv_ch = int(pkt_str[12:15])
    return data.rstrip(), seqnum, lastseq, rcv_ch

def verify_checksum(data, seqnum, lastseq, rcv_ch):
    seq_s = f"{seqnum:04d}"
    last_s = f"{lastseq:04d}"
    calc = checksum_for(data.ljust(PAYLOAD_SIZE) + seq_s + last_s) % 256
    print(f"[CHECKSUM] calc={calc} recv={rcv_ch}")
    return calc == rcv_ch

def send_ack(client_conn, seqnum):
    pkt = make_pkt("ACK", seqnum, 0)
    client_conn.sendall(pkt.encode())
    print(f"[SENT ACK] seq={seqnum}")

def send_nak(client_conn, seqnum):
    pkt = make_pkt("NAK", seqnum, 0)
    client_conn.sendall(pkt.encode())
    print(f"[SENT NAK] seq={seqnum}")

# ---------- Handshake ----------
def handshake(conn):
    """
    Recebe um SYN do cliente no formato:
      "SYN|MODE|MAXMSG"
    MODE: "GBN" ou "SR"
    MAXMSG: inteiro >= 30
    Responde: "SYN-ACK|WINDOW" (WINDOW definido pelo servidor: 1..5, default 5)
    Aguarda "ACK"
    """
    try:
        raw = conn.recv(1024).decode()
    except Exception as e:
        print("[HANDSHAKE] erro ao receber:", e)
        return None

    if not raw:
        return None
    parts = raw.split("|")
    if parts[0] != "SYN" or len(parts) < 3:
        print("[HANDSHAKE] formato invalido do SYN")
        return None

    mode = parts[1]
    try:
        maxmsg = int(parts[2])
    except:
        print("[HANDSHAKE] MAXMSG invalido")
        return None

    # server escolhe window (especificação: valor inicial 5)
    WINDOW = 5
    synack = f"SYN-ACK|{WINDOW}"
    conn.sendall(synack.encode())
    conn.settimeout(3.0)
    try:
        ack = conn.recv(1024).decode()
        if ack == "ACK":
            conn.settimeout(None)
            print(f"[HANDSHAKE COMPLETE] mode={mode} maxmsg={maxmsg} window={WINDOW}")
            return {"mode": mode, "maxmsg": maxmsg, "window": WINDOW}
        else:
            print("[HANDSHAKE] ACK inválido")
            return None
    except socket.timeout:
        print("[HANDSHAKE] timeout aguardando ACK")
        return None
    finally:
        conn.settimeout(None)

# ---------- Listeners ----------
def listener_individual(conn):
    """
    Confirmação individual: para cada pacote recebido, envia ACK ou NAK.
    Espera pacotes sequenciais diretos (1,2,3,...). Concatenates payloads
    até seq == lastseq e então imprime a mensagem completa.
    """
    try:
        full_message = ""
        while True:
            raw = conn.recv(1024).decode()
            if not raw:
                print("[DISCONNECTED] client desconectou")
                break
            # assume que cada recv trará pacotes completos (sem perdas/erros para 27/10)
            try:
                data, seqnum, lastseq, rcv_ch = parse_pkt(raw)
            except ValueError as e:
                print("[PARSE ERROR]", e)
                continue

            print(f"[RECEIVED] data='{data}', seq={seqnum}, last={lastseq}")
            if verify_checksum(data, seqnum, lastseq, rcv_ch):
                full_message += data
                send_ack(conn, seqnum)
                if seqnum == lastseq:
                    print(f"\n[FULL MESSAGE] {full_message}\n")
                    full_message = ""
            else:
                send_nak(conn, seqnum)
    except Exception as e:
        print("[EXCEPTION]", e)

def listener_window(conn, window_size):
    """
    Confirma por janela: espera receber até 'window_size' pacotes,
    se todos estiverem corretos envia ACK com último seq da janela.
    Para o checkpoint 27/10 assumimos canal sem perdas/erros então esse fluxo segue normal.
    """
    try:
        full_message = ""
        buffer = ""  # string accumulator para bytes recebidos
        temp = {}    # seqnum -> data
        packets_received = []
        expected_seq = 1

        while True:
            raw = conn.recv(4096).decode()
            if not raw:
                print("[DISCONNECTED] cliente desconectado")
                break
            buffer += raw
            # processar pacotes completos no buffer
            while len(buffer) >= PKT_LEN:
                pkt = buffer[:PKT_LEN]
                buffer = buffer[PKT_LEN:]
                try:
                    data, seqnum, lastseq, rcv_ch = parse_pkt(pkt)
                except ValueError as e:
                    print("[PARSE ERROR]", e)
                    continue

                print(f"[RECEIVED] data='{data}', seq={seqnum}, last={lastseq}")
                if seqnum != expected_seq:
                    # Em canal sem perdas/erros isso não deverá ocorrer para o checkpoint 27/10,
                    # Mas implementamos resposta NAK genérica.
                    print("[ERROR] packet out of expected order -> NAK")
                    send_nak(conn, expected_seq)
                    # reset state for window
                    temp.clear()
                    packets_received = []
                    buffer = ""
                    expected_seq = (expected_seq - 1) // window_size * window_size + 1
                    break

                if verify_checksum(data, seqnum, lastseq, rcv_ch):
                    temp[seqnum] = data
                    packets_received.append(seqnum)
                    expected_seq += 1
                else:
                    print(f"[ERROR] checksum invalido seq {seqnum}")
                    send_nak(conn, seqnum)
                    # reset state window
                    temp.clear()
                    packets_received = []
                    expected_seq = (seqnum - 1) // window_size * window_size + 1
                    buffer = ""
                    break

                # decisão: se atingimos janela completa ou fim da mensagem
                if (len(packets_received) == window_size) or (seqnum == lastseq):
                    # se todos OK -> ACK com ultimo seq
                    if len(packets_received) > 0 and all(s in temp for s in sorted(packets_received)):
                        last_of_window = max(packets_received)
                        send_ack(conn, last_of_window)
                        print("[GROUP ACK SENT] last =", last_of_window)
                        # concatenar em ordem
                        for s in sorted(packets_received):
                            full_message += temp[s]
                        temp.clear()
                        packets_received = []
                        if seqnum == lastseq:
                            print(f"\n[FULL MESSAGE] {full_message}\n")
                            full_message = ""
                            expected_seq = 1
                    else:
                        # NAK com seq inicial da janela
                        if packets_received:
                            send_nak(conn, packets_received[0])
                            print("[GROUP NAK SENT]")
                        temp.clear()
                        packets_received = []
                        expected_seq = (seqnum - 1) // window_size * window_size + 1

    except Exception as e:
        print("[EXCEPTION]", e)

# ---------- Interface do servidor ----------
def server_interface(conn, params):
    menu = """
[1] Packet Individual Confirmation
[2] Packet Group (window) Confirmation
[3] Close connection
"""
    while True:
        print(menu)
        choice = input("Choose option:\n>>> ").strip()
        if choice == '1':
            listener_individual(conn)
        elif choice == '2':
            listener_window(conn, params["window"])
        elif choice == '3':
            print("[SERVER] Closing session with client.")
            return
        else:
            print("[INVALID OPTION]")

# ---------- Main server ----------
def start_server(host='localhost', port=65432):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen()
    print(f"[SERVER] listening on {host}:{port}")

    try:
        while True:
            conn, addr = s.accept()
            print(f"[CONNECTED] from {addr}")
            with conn:
                params = handshake(conn)
                if params:
                    server_interface(conn, params)
                else:
                    print("[HANDSHAKE FAILED] closing connection")
                    conn.close()
    except KeyboardInterrupt:
        print("[SERVER] interrupted, closing.")
    finally:
        s.close()

if __name__ == "__main__":
    start_server()
