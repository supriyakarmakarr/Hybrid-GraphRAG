"""
Generate RSA 2048-bit key pair for JWT signing (RS256).
Supports cryptography module with fallback to system ssh-keygen.
Run once: python scripts/generate_keys.py
"""
import os
import subprocess
from pathlib import Path

def generate_rsa_keys():
    keys_dir = Path("keys")
    keys_dir.mkdir(exist_ok=True)

    private_path = keys_dir / "private.pem"
    public_path  = keys_dir / "public.pem"

    if private_path.exists() and public_path.exists():
        print("✓ Keys already exist in keys/ (private.pem, public.pem).")
        return

    # Method 1: Try cryptography Python library
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        private_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

        public_path.write_bytes(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )

        print(f"✓ RSA keys generated via cryptography:")
        print(f"  Private: {private_path}")
        print(f"  Public:  {public_path}")
        return

    except ImportError:
        pass

    # Method 2: Fallback to ssh-keygen (present on Windows 10/11, macOS, Linux)
    try:
        tmp_key = keys_dir / "temp_key"
        if tmp_key.exists():
            tmp_key.unlink()

        # Generate private key
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "2048", "-m", "PEM", "-f", str(private_path), "-N", "", "-q"],
            check=True
        )

        # Export public key in PKCS8 PEM format
        result = subprocess.run(
            ["ssh-keygen", "-e", "-m", "PKCS8", "-f", str(private_path)],
            capture_output=True,
            text=True,
            check=True
        )
        public_path.write_text(result.stdout, encoding="utf-8")

        # Clean any pub files created by ssh-keygen
        pub_aux = keys_dir / "private.pem.pub"
        if pub_aux.exists():
            pub_aux.unlink()

        print(f"✓ RSA keys generated via ssh-keygen fallback:")
        print(f"  Private: {private_path}")
        print(f"  Public:  {public_path}")

    except Exception as e:
        print(f"Failed to generate keys automatically: {e}")
        print("Manual command:")
        print("  ssh-keygen -t rsa -b 2048 -m PEM -f keys/private.pem -N ''")
        print("  ssh-keygen -e -m PKCS8 -f keys/private.pem > keys/public.pem")
        raise


if __name__ == "__main__":
    generate_rsa_keys()
