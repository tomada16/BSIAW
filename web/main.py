#!/usr/bin/env python3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from typing import Optional, Self
import datetime
import hashlib
import flask
import psycopg2
import time
import os

SESSION_TIMEOUT = 120

app = Flask(__name__)
# Temporary will be changed when sesions are done | "secret" will be later deleted
app.secret_key = "secret"

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="localhost", database="bsiaw", user="postgres", password=""
)


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

        if self.exists():
            self.load()

    @classmethod
    def from_session_key(cls, key) -> Optional[Self]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM sessions WHERE session_key=%s", (key,)
            )
            r = cur.fetchone()
            if not r:
                return None
            user_id = r[0]
            cur.execute("SELECT email, login FROM users WHERE id=%s", (user_id,))
            r = cur.fetchone()
            if not r:
                return None
            return cls(r[0],r[1])

    @staticmethod
    def get_all_emails():
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM users")
            r = cur.fetchall()
            return [x[0] for x in r]

    def exists(self):
        """Returns True if the user exists in the database."""
        with conn.cursor() as cur:
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

        with conn.cursor() as cur:
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
        with conn.cursor() as cur:
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

        conn.commit()

    def __get_session(self) -> Optional[Session]:
        """Returns the session data for this user, or None."""
        with conn.cursor() as cur:
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
        with conn.cursor() as cur:
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

        conn.commit()

        # ------------------------------------------------------------
        # Friends helpers
        # ------------------------------------------------------------
        def get_friend_emails(self):
            """
            Returns a list of friend emails for this user.
            Works directly on the friendships table (does not require the view).
            """
            if self.user_id is None:
                return []
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.email
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
                return [r[0] for r in rows]

    # ------------------------------------------------------------
    # Friends helpers
    # ------------------------------------------------------------
    def get_friend_emails(self):
        """
        Returns a list of friend emails for this user.
        Works directly on the friendships table (does not require the view).
        """
        if self.user_id is None:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.email
                FROM public.friendships f
                JOIN public.users u
                  ON u.id = CASE
                               WHEN f.user_id_low = %s THEN f.user_id_high
                               ELSE f.user_id_low
                            END
                WHERE %s IN (f.user_id_low, f.user_id_high)
                ORDER BY u.email""",
                (self.user_id, self.user_id),
            )
            rows = cur.fetchall()
            return [r[0] for r in rows]

@app.route("/")
def index():
    if "token" not in request.cookies:
        return redirect(url_for("login"))

    token = request.cookies["token"]
    user = User.from_session_key(token)
    if not user or user.user_id is None or not user.check_session(token):
        return redirect(url_for("login"))

    # Show friends of the logged-in user on index.html.
    # Template expects `usernames` -> pass friend emails there.
    usernames = user.get_friend_emails()

    return render_template(
        "index.html",
        user_email=user.email,
        session_timeout=SESSION_TIMEOUT,
        usernames=usernames,
    )


@app.route("/logout", methods=["GET"])
def logout():
    r = redirect(url_for("login"))
    for cookie in request.cookies:
        r.delete_cookie(cookie)
    return r


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"]
    password = request.form["password"]

    if not email or not password:
        flash("Brakuje jednego z pól", "error")
        return render_template("bad_request.html"), 401

    user = User(email)
    if not user.user_id or not user.check_password(password):
        flash("Zły e-mail lub hasło", "error")
        return redirect(url_for("login"))

    user.create_session(SESSION_TIMEOUT)

    flash("Witaj {}".format(email), "success")

    r = flask.make_response(redirect(url_for("index")))
    r.set_cookie(
        "token", user.get_session_key(), httponly=True, samesite="Strict"
    )
    return r


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    login = request.form["login"]
    email = request.form["email"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]

    if not all([login, email, password, confirm_password]):
        flash("Brak wszystkich wymaganych pól","error")
        return redirect(url_for("register"))

    if password != confirm_password:
        flash("Hasła nie są takie same!", "error")
        return redirect(url_for("register"))

    user = User(email, login)
    if user.user_id:
        flash("Użytkownik już istnieje.", "error")
        return redirect(url_for("register"))

    user.set_password(password)
    user.save()
    flash("Zarejestrowano pomyślnie!", "success")
    return redirect(url_for("login"))


@app.route("/lib/<path:filename>", methods=["GET"])
def lib(filename):
    return send_from_directory("lib", filename)
