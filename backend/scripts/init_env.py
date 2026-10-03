"""Create local configuration with a random JWT key without printing secrets."""

import secrets
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
destination = backend_dir / ".env"
if destination.exists():
    print("backend/.env already exists; left unchanged.")
else:
    template = (backend_dir / ".env.example").read_text(encoding="utf-8")
    template = template.replace("JWT_SECRET=\n", f"JWT_SECRET={secrets.token_urlsafe(48)}\n")
    destination.write_text(template, encoding="utf-8", newline="\n")
    print("Created backend/.env with a random JWT secret.")
