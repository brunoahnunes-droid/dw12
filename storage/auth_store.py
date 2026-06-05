"""Username/password authentication backed by data/users.json.

Passwords are stored as werkzeug PBKDF2-SHA256 hashes — never in plain text.
A default admin account is created automatically on first run.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

_FILE         = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")
_DEFAULT_USER = "admin"
_DEFAULT_PASS = "loterias2026"


class AuthStore:
    def __init__(self) -> None:
        self._data: dict = self._load()
        self._ensure_default()

    def _load(self) -> dict:
        if os.path.exists(_FILE):
            try:
                with open(_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"users": []}

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _ensure_default(self) -> None:
        if not self._data.get("users"):
            self._data["users"] = [{
                "username":     _DEFAULT_USER,
                "password_hash": generate_password_hash(_DEFAULT_PASS),
                "role":         "admin",
            }]
            self._flush()

    # ── public API ────────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> bool:
        raw = self._get_raw(username)
        return bool(raw) and check_password_hash(raw["password_hash"], password)

    def change_password(self, username: str,
                        old_password: str, new_password: str) -> bool:
        if not self.authenticate(username, old_password):
            return False
        for user in self._data["users"]:
            if user["username"] == username:
                user["password_hash"] = generate_password_hash(new_password)
                self._flush()
                return True
        return False

    def get_user(self, username: str) -> Optional[dict]:
        raw = self._get_raw(username)
        return {"username": raw["username"],
                "role":     raw.get("role", "user")} if raw else None

    def create_user(self, username: str, password: str,
                    role: str = "user") -> bool:
        if self._get_raw(username):
            return False
        self._data.setdefault("users", []).append({
            "username":     username,
            "password_hash": generate_password_hash(password),
            "role":         role,
        })
        self._flush()
        return True

    def delete_user(self, username: str) -> bool:
        before = len(self._data["users"])
        self._data["users"] = [
            u for u in self._data["users"] if u["username"] != username
        ]
        if len(self._data["users"]) < before:
            self._flush()
            return True
        return False

    def list_users(self) -> List[dict]:
        return [{"username": u["username"], "role": u.get("role", "user")}
                for u in self._data.get("users", [])]

    def _get_raw(self, username: str) -> Optional[dict]:
        for u in self._data.get("users", []):
            if u["username"] == username:
                return u
        return None
