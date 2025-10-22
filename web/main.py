#!/usr/bin/env python3

import eventlet; eventlet.monkey_patch()
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    abort,
)
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from typing import Optional, Self, List, Tuple
import datetime
import hashlib
import flask
import psycopg2
import time
import os
import sys


SESSION_TIMEOUT = 120
MAX_MESSAGE_LEN = 2000

app = Flask(__name__)
# Temporary will be changed when sesions are done | "secret" will be later deleted
app.secret_key = "secret"

# Socket.IO setup (uses cookies for auth; CORS same-origin by default)
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

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
            return cls(r[0], r[1])

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

    def __get_session(self) -> Optional["Session"]:
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
    def get_friends(self) -> List[Tuple[int, str]]:
        """Returns (friend_id, friend_email) for this user."""
        if self.user_id is None:
            return []
        with conn.cursor() as cur:
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
        with conn.cursor() as cur:
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


# ------------------------------------------------------------
# Helpers for HTTP + Socket handlers
# ------------------------------------------------------------
def _require_user():
    """Small helper to fetch the logged-in user from cookie or redirect."""
    if "token" not in request.cookies:
        return None
    token = request.cookies["token"]
    user = User.from_session_key(token)
    if not user or user.user_id is None or not user.check_session(token):
        return None
    return user


def _current_user_ws():
    """Auth for Socket.IO: read cookie token and validate session."""
    token = request.cookies.get("token")
    if not token:
        return None
    user = User.from_session_key(token)
    if not user or user.user_id is None or not user.check_session(token):
        return None
    return user


def _dm_room(a: int, b: int) -> str:
    """Stable room name for a pair of users (undirected)."""
    low, high = (a, b) if a < b else (b, a)
    return f"dm:{low}:{high}"


# ------------------------------------------------------------
# HTTP pages
# ------------------------------------------------------------
@app.route("/")
def index():
    user = _require_user()
    if user is None:
        return redirect(url_for("login"))

    friends = user.get_friends()
    return render_template(
        "index.html",
        user_email=user.email,
        session_timeout=SESSION_TIMEOUT,
        friends=friends,
        selected_friend=None,
        current_user_id=user.user_id,
    )


@app.route("/chat/<int:friend_id>")
def chat(friend_id: int):
    user = _require_user()
    if user is None:
        return redirect(url_for("login"))
    if friend_id == user.user_id or not user.is_friend_with(friend_id):
        abort(404)

    with conn.cursor() as cur:
        cur.execute("SELECT id, email FROM public.users WHERE id=%s", (friend_id,))
        row = cur.fetchone()
        if not row:
            abort(404)
        friend = {"id": row[0], "email": row[1]}

    friends = user.get_friends()
    return render_template(
        "index.html",
        user_email=user.email,
        session_timeout=SESSION_TIMEOUT,
        friends=friends,
        selected_friend=friend,
        current_user_id=user.user_id,
    )


# ------------------------------------------------------------
# Socket.IO events (WebSocket)
# ------------------------------------------------------------
@socketio.on("connect")
def ws_connect():
    user = _current_user_ws()
    print(f"[ws][connect] user={'NONE' if not user else user.user_id}", file=sys.stderr, flush=True)
    if user is None:
        return False  # reject


@socketio.on("join")
def ws_join(data):
    """
    Join a DM room and receive recent history.
    data = { "friend_id": int }
    """
    user = _current_user_ws()
    print(f"[ws][join] user={'NONE' if not user else user.user_id} data={data}", file=sys.stderr, flush=True)
    if user is None:
        return disconnect()

    friend_id = int(data.get("friend_id", 0))
    if friend_id == 0 or friend_id == user.user_id or not user.is_friend_with(friend_id):
        print(f"[ws][join] reject: friend_id={friend_id}", file=sys.stderr, flush=True)
        return  # ignore silently

    room = _dm_room(user.user_id, friend_id)
    join_room(room)
    print(f"[ws][join] joined room {room}", file=sys.stderr, flush=True)

    # Load last 50 messages for this conversation
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, sender_id, receiver_id, body, created_at
            FROM public.messages
            WHERE (sender_id=%s AND receiver_id=%s)
               OR (sender_id=%s AND receiver_id=%s)
            ORDER BY id DESC
            LIMIT 50
            """,
            (user.user_id, friend_id, friend_id, user.user_id),
        )
        rows = cur.fetchall()[::-1]  # chronological

    history = [
        {
            "id": mid,
            "sender_id": sid,
            "body": body,
            "created_at": created_at.isoformat()
        }
        for (mid, sid, rid, body, created_at) in rows
    ]
    emit("history", {"messages": history})


@socketio.on("send_message")
def ws_send_message(data):
    """
    Send a message to the current friend; broadcast to room.
    data = { "friend_id": int, "body": str }
    """
    user = _current_user_ws()
    print(f"[ws][send] user={'NONE' if not user else user.user_id} data={data}", file=sys.stderr, flush=True)
    if user is None:
        return disconnect()

    try:
        friend_id = int(data.get("friend_id"))
    except Exception:
        print("[ws][send] bad friend_id", file=sys.stderr, flush=True)
        return
    body = (data.get("body") or "").strip()

    if not body or len(body) > MAX_MESSAGE_LEN:
        print("[ws][send] empty body", file=sys.stderr, flush=True)
        return
    if friend_id == user.user_id or not user.is_friend_with(friend_id):
        print(f"[ws][send] not friends or self: friend_id={friend_id}", file=sys.stderr, flush=True)
        return

    # Persist to DB
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.messages (sender_id, receiver_id, body)
            VALUES (%s, %s, %s)
            RETURNING id, created_at
            """,
            (user.user_id, friend_id, body),
        )
        mid, created_at = cur.fetchone()
    conn.commit()

    print(f"[ws][send] saved mid={mid}", file=sys.stderr, flush=True)

    room = _dm_room(user.user_id, friend_id)
    join_room(room)

    payload = {
        "id": mid,
        "body": body,
        "created_at": created_at.isoformat(),
        "sender_id": user.user_id,
    }

    emit("message", payload, room=room)
    print(f"[ws][send] emitted to {room}", file=sys.stderr, flush=True)


# ------------------------------------------------------------
# Legacy HTTP API (optional) — can be kept or removed
# ------------------------------------------------------------
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
    flash("Zarejestrowno pomyślnie!", "success")
    return redirect(url_for("login"))


@app.route("/lib/<path:filename>", methods=["GET"])
def lib(filename):
    return send_from_directory("lib", filename)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    # Enable debug + code reloader inside Docker.
    # NOTE: The reloader watches files in the container filesystem.
    #       Mount your project directory as a volume to get "live" changes.
    socketio.run(
        app,
        host="0.0.0.0",
        port=80,
        debug=True,          # Flask debug (autoreload)
        use_reloader=False    # Force reloader for SocketIO server
    )
