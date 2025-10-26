import socket

PAYLOAD_SIZE = 4
PKT_LEN = 4 + 4 + 4 + 3 

def checksum_for(data_str):
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
    return calc == rcv_ch

def send_ack(client_conn, seqnum):
    pkt = make_pkt("ACK", seqnum, 0)
    client_conn.sendall(pkt.encode())
    print(f"[SENT ACK] seq={seqnum}")

def send_nak(client_conn, seqnum):
    pkt = make_pkt("NAK", seqnum, 0)
    client_conn.sendall(pkt.encode())
    print(f"[SENT NAK] seq={seqnum}")

def handshake(conn):
    try:
        raw = conn.recv(1024).decode()
    except Exception as e:
        print("[HANDSHAKE] erro ao receber:", e)
        return None

    if not raw:
        return None

    parts = raw.split("|")
    if len(parts) < 3 or parts[0] != "SYN":
        print("[HANDSHAKE] formato invalido")
        return None

    mode = parts[1]
    try:
        maxmsg = int(parts[2])
    except:
        maxmsg = 30

    WINDOW = 5
    conn.sendall(f"SYN-ACK|{WINDOW}".encode())

    conn.settimeout(3.0)
    try:
        ack = conn.recv(1024).decode()
        if ack == "ACK":
            print(f"[HANDSHAKE OK] mode={mode} maxmsg={maxmsg} window={WINDOW}")
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
    full_message = ""
    while True:
        raw = conn.recv(1024).decode()
        if not raw:
            print("[CLIENTE DESCONECTOU]")
            break

        data, seqnum, lastseq, rcv_ch = parse_pkt(raw)
        print(f"[RECEIVED] data='{data}', seq={seqnum}, last={lastseq}")

        if verify_checksum(data, seqnum, lastseq, rcv_ch):
            send_ack(conn, seqnum)
            full_message += data
            if seqnum == lastseq:
                print(f"\n[FULL MESSAGE RECEIVED]\n{full_message}\n")
                break
        else:
            send_nak(conn, seqnum)

def listener_window(conn, window_size):
    full_message = ""
    buffer = ""
    temp = {}
    packets_received = []

    while True:
        raw = conn.recv(4096).decode()
        if not raw:
            print("[CLIENTE DESCONECTOU]")
            break

        buffer += raw

        while len(buffer) >= PKT_LEN:
            pkt = buffer[:PKT_LEN]
            buffer = buffer[PKT_LEN:]
            data, seqnum, lastseq, rcv_ch = parse_pkt(pkt)
            print(f"[RECEIVED] data='{data}', seq={seqnum}, last={lastseq}")

            if not verify_checksum(data, seqnum, lastseq, rcv_ch):
                send_nak(conn, seqnum)
                continue

            temp[seqnum] = data
            packets_received.append(seqnum)

            if len(packets_received) == window_size or seqnum == lastseq:
                send_ack(conn, max(packets_received))
                print(f"[GROUP ACK SENT] last={max(packets_received)}")

                for s in sorted(packets_received):
                    full_message += temp[s]
                temp.clear()
                packets_received.clear()

                if seqnum == lastseq:
                    print(f"\n[FULL MESSAGE RECEIVED]\n{full_message}\n")
                    return

# ---------- Main ----------
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
                if not params:
                    print("[HANDSHAKE FAILED]")
                    conn.close()
                    continue

                mode = params["mode"].upper()
                if mode == "GBN":
                    print("[SERVER MODE] Go-Back-N (window)")
                    listener_window(conn, params["window"])
                elif mode == "SR":
                    print("[SERVER MODE] Stop-and-Wait / SR")
                    listener_individual(conn)
                else:
                    print(f"[SERVER MODE] desconhecido ({mode}), usando individual.")
                    listener_individual(conn)

                print("[SERVER] Sessão finalizada. Aguardando novo cliente...\n")

    except KeyboardInterrupt:
        print("\n[SERVER] encerrado manualmente.")
    finally:
        s.close()

if __name__ == "__main__":
    start_server()
