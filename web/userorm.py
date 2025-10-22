# User & Session ORM classes for project
# Copyright (c) 2025 Politechnika Wrocławska

from typing import Optional, Self, List, Tuple
from . import db
import psycopg2
import datetime
import hashlib
import time
import os


class Session:
    """Represents a session object. Used internally in User."""

    key: str
    timeout: int

    def __init__(self, key, timeout):
        self.key = key
        self.timeout = timeout


class User:
    """ORM representation of a user. If the user already exists, it will be
    automatically loaded from the database when calling the constructor."""

    user_id: int
    login: str
    email: str
    password_hash: str
    password_salt: str

    def __init__(self, email: str, login: str = None):
        self.user_id = None
        self.email = email
        self.login = login
        self.password_hash = None
        self.password_salt = None
        self.conn = db.create_connection()

        if self.exists():
            self.load()

    @classmethod
    def from_session_key(cls, key) -> Optional[Self]:
        with db.create_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM sessions WHERE session_key=%s", (key,)
                )
                r = cur.fetchone()
                if not r:
                    return None
                user_id = r[0]
                cur.execute(
                    "SELECT email, login FROM users WHERE id=%s", (user_id,)
                )
                r = cur.fetchone()
                if not r:
                    return None
                return cls(r[0], r[1])

    def exists(self):
        """Returns True if the user exists in the database."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (self.email,))
            return cur.fetchone() is not None

    def check_password(self, passwd):
        """Check the password for the user. Returns True if it matches the one
        in the database."""
        passwd_hash = hashlib.sha256(
            bytes(passwd + self.password_salt, "utf8")
        ).hexdigest()
        return passwd_hash == self.password_hash

    def set_password(self, passwd):
        """Create a new password salt & hash for the user."""
        self.password_salt = os.getrandom(8, os.GRND_RANDOM).hex()
        self.password_hash = hashlib.sha256(
            bytes(passwd + self.password_salt, "utf8")
        ).hexdigest()

    def load(self):
        """Loads the user data from the database. Does not throw if the user
        does not exist."""

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, login, email, password_hash, password_salt FROM "
                "users WHERE email=%s",
                (self.email,),
            )
            res = cur.fetchone()
            if not res:
                return

            (
                self.user_id,
                self.login,
                self.email,
                self.password_hash,
                self.password_salt,
            ) = res

    def save(self):
        """Store the data back into the database."""
        with self.conn.cursor() as cur:
            if self.exists():
                raise NotImplementedError("cannot modify user")
            else:
                cur.execute(
                    "INSERT INTO users (login, email, password_hash, "
                    "password_salt) VALUES (%s, %s, %s, %s)",
                    (
                        self.login,
                        self.email,
                        self.password_hash,
                        self.password_salt,
                    ),
                )

        self.conn.commit()

    def __get_session(self) -> Optional["Session"]:
        """Returns the session data for this user, or None."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT session_key, valid_until FROM sessions WHERE user_id=%s",
                (self.user_id,),
            )
            data = cur.fetchone()
            if not data:
                return None
            return Session(data[0], data[1].timestamp())

    def get_session_key(self) -> Optional[str]:
        s = self.__get_session()
        return s.key if s is not None else None

    def check_session(self, session_key) -> bool:
        """Compares the given `session_key` to the one in the sessions table,
        and checks the timeout value. Returns True if its valid."""
        s = self.__get_session()
        if not s or s.key != session_key:
            return False
        return time.time() <= s.timeout

    def create_session(self, timeout_sec):
        """Create a session for the user."""
        with self.conn.cursor() as cur:
            if self.__get_session():
                cur.execute(
                    "DELETE FROM sessions WHERE user_id=%s", (self.user_id,)
                )

            k = os.getrandom(16, os.GRND_RANDOM).hex()
            t = datetime.datetime.fromtimestamp(int(time.time()) + timeout_sec)
            cur.execute(
                "INSERT INTO sessions (session_key, valid_until, user_id) VALUES (%s, %s, %s)",
                (k, t, self.user_id),
            )

        self.conn.commit()

    # ------------------------------------------------------------
    # Friends helpers
    # ------------------------------------------------------------
    def get_friends(self) -> List[Tuple[int, str]]:
        """Returns (friend_id, friend_email) for this user."""
        if self.user_id is None:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email
                FROM public.friendships f
                JOIN public.users u
                  ON u.id = CASE
                               WHEN f.user_id_low = %s THEN f.user_id_high
                               ELSE f.user_id_low
                            END
                WHERE %s IN (f.user_id_low, f.user_id_high)
                ORDER BY u.email
                """,
                (self.user_id, self.user_id),
            )
            rows = cur.fetchall()
            return [(r[0], r[1]) for r in rows]

    def is_friend_with(self, other_user_id: int) -> bool:
        """Returns True if `other_user_id` is a friend of this user."""
        if self.user_id is None:
            return False
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM public.friendships f
                WHERE (%s = f.user_id_low AND %s = f.user_id_high)
                   OR (%s = f.user_id_high AND %s = f.user_id_low)
                """,
                (
                    min(self.user_id, other_user_id),
                    max(self.user_id, other_user_id),
                    min(self.user_id, other_user_id),
                    max(self.user_id, other_user_id),
                ),
            )
            return cur.fetchone() is not None
