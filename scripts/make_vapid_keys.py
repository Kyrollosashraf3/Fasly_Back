"""Generate a VAPID key pair for web push and print the .env lines.

    python scripts/make_vapid_keys.py            # print only
    python scripts/make_vapid_keys.py --write    # also append to .env

The private key never leaves the server; the public key is what the browser
gets as ``applicationServerKey`` when it subscribes.
"""

import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ENV_KEYS = ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_CLAIMS_EMAIL")


def make_pair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    # The browser wants the point (0x04 || X || Y) base64url-encoded, unpadded.
    raw_point = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_key = base64.urlsafe_b64encode(raw_point).decode().rstrip("=")
    return public_key, private_pem


def append_to_env(values: dict[str, str]) -> Path:
    env = Path(__file__).resolve().parents[1] / ".env"
    existing = env.read_text(encoding="utf-8") if env.exists() else ""
    lines = [line for line in existing.splitlines() if line.split("=")[0].strip() not in ENV_KEYS]
    lines += [f"{key}={value}" for key, value in values.items()]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="append the keys to .env")
    parser.add_argument(
        "--email",
        default="mailto:admin@fasly.app",
        help="VAPID contact, e.g. mailto:you@church.org",
    )
    args = parser.parse_args()

    public_key, private_pem = make_pair()
    values = {
        "VAPID_PUBLIC_KEY": public_key,
        # One line: a raw PEM would be cut at its first newline by .env parsing.
        "VAPID_PRIVATE_KEY": private_pem.replace("\n", "\\n"),
        "VAPID_CLAIMS_EMAIL": args.email,
    }

    if args.write:
        print(f"written to {append_to_env(values)} (gitignored - keep it that way)")
    else:
        for key, value in values.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
