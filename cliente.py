import socket
import time

PAYLOAD_SIZE = 4
PKT_LEN = 4 + 4 + 4 + 3  # must match server

def checksum_for(data_str):
    return sum(bytearray(data_str.encode())) % 256

def make_pkt(data, seqnum, lastseq, corrupt=False):
    data_fixed = data.ljust(PAYLOAD_SIZE)[:PAYLOAD_SIZE]
    seq_s = f"{seqnum:04d}"
    last_s = f"{lastseq:04d}"
    ch = checksum_for(data_fixed + seq_s + last_s) % 256
    if corrupt:
        ch = (ch + 1) % 256
    ch_s = f"{ch:03d}"
    return f"{data_fixed}{seq_s}{last_s}{ch_s}"

def parse_pkt(pkt):
    if len(pkt) != PKT_LEN:
        raise ValueError("[PARSE ERROR] length mismatch")
    data = pkt[0:PAYLOAD_SIZE]
    seqnum = int(pkt[4:8])
    # lastseq for ACK/NAK not used on client
    # lastseq = int(pkt[8:12])
    rcv_ch = int(pkt[12:15])
    return data.rstrip(), seqnum, rcv_ch

def verify_checksum(data, seqnum, rcv_ch):
    seq_s = f"{seqnum:04d}"
    calc = checksum_for(data.ljust(PAYLOAD_SIZE) + seq_s + "0000") % 256
    # note: ACK/NAK packets were created with lastseq==0 on server; consistent
    return calc == rcv_ch

# ---------- Handshake ----------
def do_handshake(sock, mode, maxmsg):
    syn = f"SYN|{mode}|{maxmsg}"
    sock.sendall(syn.encode())
    sock.settimeout(3.0)
    try:
        synack = sock.recv(1024).decode()
        parts = synack.split("|")
        if parts[0] != "SYN-ACK":
            print("[HANDSHAKE] invalid SYN-ACK")
            return None
        window = int(parts[1])
        sock.sendall("ACK".encode())
        sock.settimeout(None)
        print(f"[HANDSHAKE COMPLETE] server window={window}")
        return {"mode": mode, "maxmsg": maxmsg, "window": window}
    except socket.timeout:
        print("[HANDSHAKE] timeout waiting SYN-ACK")
        return None
    finally:
        sock.settimeout(None)

# ---------- Receiving ACK/NAK ----------
def recv_ack_nak(sock, timeout=2.0):
    sock.settimeout(timeout)
    try:
        pkt = sock.recv(1024).decode()
        if not pkt:
            return None, "NO_DATA"
        data, seqnum, rcv_ch = parse_pkt(pkt)
        # server sent ACK/NAK with lastseq==0
        valid = verify_checksum(data, seqnum, rcv_ch)
        print(f"[RECEIVED] {data} seq={seqnum} checksum_ok={valid}")
        if not valid:
            return seqnum, "BAD_CHECKSUM"
        if data == "ACK":
            return seqnum, "ACK"
        elif data == "NAK":
            return seqnum, "NAK"
        else:
            return seqnum, "UNKNOWN"
    except socket.timeout:
        return None, "TIMEOUT"
    finally:
        sock.settimeout(None)

# ---------- Sending (no-losses scenario; supports window and individual) ----------
def send_individual(sock):
    message = input("Enter message (min 30 chars):\n>>> ")
    if len(message) < 30:
        print("[ERROR] message below min length 30")
        return
    packets = [message[i:i+PAYLOAD_SIZE] for i in range(0, len(message), PAYLOAD_SIZE)]
    lastseq = len(packets)
    for idx, pkt_data in enumerate(packets, start=1):
        pkt = make_pkt(pkt_data, idx, lastseq)
        sock.sendall(pkt.encode())
        print(f"[SENT] seq={idx} data='{pkt_data}'")
        seq, resp = recv_ack_nak(sock, timeout=2.0)
        if resp == "ACK":
            continue
        else:
            # para o checkpoint 27/10 assume-se canal sem perdas/erros,
            # mas aqui trataremos um simples reenvio em caso de timeout/NAK.
            attempts = 0
            while resp != "ACK" and attempts < 3:
                print(f"[RESEND] seq={idx} attempt={attempts+1}")
                sock.sendall(pkt.encode())
                seq, resp = recv_ack_nak(sock, timeout=2.0)
                attempts += 1
            if resp != "ACK":
                print(f"[ERROR] could not get ACK for seq {idx}")

def send_window(sock, window_size):
    message = input("Enter message (min 30 chars):\n>>> ")
    if len(message) < 30:
        print("[ERROR] message below min length 30")
        return
    packets = [message[i:i+PAYLOAD_SIZE] for i in range(0, len(message), PAYLOAD_SIZE)]
    lastseq = len(packets)
    i = 0
    while i < len(packets):
        # send window
        window_packets = packets[i:i+window_size]
        seq_start = i + 1
        for j, pdata in enumerate(window_packets, start=seq_start):
            pkt = make_pkt(pdata, j, lastseq)
            sock.sendall(pkt.encode())
            print(f"[SENT] seq={j} data='{pdata}'")
        # wait for ACK of last in window (normal no-losses case)
        ack_seq, resp = recv_ack_nak(sock, timeout=3.0)
        if resp == "ACK" and ack_seq == seq_start + len(window_packets) - 1:
            print(f"[WINDOW ACK] last={ack_seq}")
            i += window_size
        else:
            # Try simple retransmit (for checkpoint 27/10, should not happen)
            print("[WINDOW] timeout or NAK; retransmitting window")
            # in Go-Back-N would retransmit whole window; in SR would retransmit only NAKed
            # Here do a simple retransmit attempt up to 3 times:
            attempts = 0
            while attempts < 3 and not (resp == "ACK" and ack_seq == seq_start + len(window_packets) - 1):
                for j, pdata in enumerate(window_packets, start=seq_start):
                    pkt = make_pkt(pdata, j, lastseq)
                    sock.sendall(pkt.encode())
                    print(f"[RESENT] seq={j}")
                ack_seq, resp = recv_ack_nak(sock, timeout=3.0)
                attempts += 1
            if not (resp == "ACK" and ack_seq == seq_start + len(window_packets) - 1):
                print("[ERROR] window failed after retries")
                return

# ---------- Interface ----------
def client_interface(sock, params):
    while True:
        menu = f"""
[1] Send message (individual confirmation)
[2] Send message (window confirmation)  -- server window={params['window']}
[3] Close
"""
        print(menu)
        choice = input("Choose option:\n>>> ").strip()
        if choice == '1':
            send_individual(sock)
        elif choice == '2':
            send_window(sock, params['window'])
        elif choice == '3':
            print("[CLIENT] closing")
            sock.close()
            return
        else:
            print("[INVALID OPTION]")

# ---------- Main ----------
def main(server_host='localhost', server_port=65432):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((server_host, server_port))
        print(f"[CONNECTED] to {server_host}:{server_port}")
        # Escolha do modo e maxmsg (exigido no handshake)
        mode = input("Choose mode (GBN or SR): ").strip().upper()
        if mode not in ("GBN", "SR"):
            print("[INVALID MODE] defaulting to GBN")
            mode = "GBN"
        try:
            maxmsg = int(input("Max message size (>=30): ").strip())
            if maxmsg < 30:
                print("[ERROR] must be >= 30, using 30")
                maxmsg = 30
        except:
            maxmsg = 30

        params = do_handshake(s, mode, maxmsg)
        if not params:
            print("[HANDSHAKE FAILED]")
            return
        client_interface(s, params)

if __name__ == "__main__":
    main()
