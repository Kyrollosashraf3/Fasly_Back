"""db package - database connection layer (Firebase/Firestore)."""

from .firebase import db, get_db, init_firebase

__all__ = [
    "db",
    "init_firebase",
    "get_db",
]
