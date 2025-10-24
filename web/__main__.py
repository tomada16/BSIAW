# Main server controller
# Copyright (c) 2025 Politechnika Wrocławska

from . import userorm, db, settings
import werkzeug.exceptions
import flask_socketio
import flask
import sys
import os

app = flask.Flask(__name__)
app.secret_key = os.getrandom(32).hex()

socketio = flask_socketio.SocketIO(
    app,
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


# ------------------------------------------------------------
# Helpers for HTTP + Socket handlers
# ------------------------------------------------------------
def _require_user():
    """Small helper to fetch the logged-in user from cookie or redirect."""
    if "token" not in flask.request.cookies:
        return None
    token = flask.request.cookies["token"]
    user = userorm.User.from_session_key(token)
    if not user or user.user_id is None or not user.check_session(token):
        return None
    return user


def _dm_room(a: int, b: int) -> str:
    """Stable room name for a pair of users (undirected)."""
    low, high = (a, b) if a < b else (b, a)
    return f"dm:{low}:{high}"


@app.errorhandler(Exception)
def error_handler(e):
    if isinstance(e, werkzeug.exceptions.HTTPException):
        return e
    return flask.render_template("bad_request.html")


# ------------------------------------------------------------
# HTTP pages
# ------------------------------------------------------------
@app.route("/")
def index():
    user = _require_user()
    if user is None:
        return flask.redirect(flask.url_for("login"))

    friends = user.get_friends()
    return flask.render_template(
        "index.html",
        user_email=user.email,
        session_timeout=settings.SESSION_TIMEOUT,
        friends=friends,
        selected_friend=None,
        current_user_id=user.user_id,
    )


@app.route("/chat/<int:friend_id>")
def chat(friend_id: int):
    user = _require_user()
    if user is None:
        return flask.redirect(flask.url_for("login"))

    if friend_id == user.user_id or not user.is_friend_with(friend_id):
        flask.abort(404)

    with db.create_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email FROM public.users WHERE id=%s", (friend_id,)
            )
            row = cur.fetchone()
            if not row:
                flask.abort(404)
            friend = {"id": row[0], "email": row[1]}

    friends = user.get_friends()
    return flask.render_template(
        "index.html",
        user_email=user.email,
        session_timeout=settings.SESSION_TIMEOUT,
        friends=friends,
        selected_friend=friend,
        current_user_id=user.user_id,
    )


# ------------------------------------------------------------
# Socket.IO events (WebSocket)
# ------------------------------------------------------------


@socketio.on("connect")
def ws_connect():
    user = _require_user()
    print(
        f"[ws][connect] user={'NONE' if not user else user.user_id}",
        file=sys.stderr,
        flush=True,
    )

    return user is not None  # reject if user does not exist with token


@socketio.on("join")
def ws_join(data):
    """
    Join a DM room and receive recent history.
    data = { "friend_id": int }
    """
    user = _require_user()
    print(
        f"[ws][join] user={'NONE' if not user else user.user_id} data={data}",
        file=sys.stderr,
        flush=True,
    )
    if user is None:
        return flask_socketio.disconnect()

    friend_id = int(data.get("friend_id", 0))
    if (
        friend_id == 0
        or friend_id == user.user_id
        or not user.is_friend_with(friend_id)
    ):
        print(
            f"[ws][join] reject: friend_id={friend_id}",
            file=sys.stderr,
            flush=True,
        )
        return  # ignore silently

    room = _dm_room(user.user_id, friend_id)
    flask_socketio.join_room(room)
    print(f"[ws][join] joined room {room}", file=sys.stderr, flush=True)

    # Load last 50 messages for this conversation
    with db.create_connection() as conn:
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
            "created_at": created_at.isoformat(),
        }
        for (mid, sid, rid, body, created_at) in rows
    ]

    flask_socketio.emit("history", {"messages": history})


@socketio.on("type_message")
def ws_type_message(data):
    user = _require_user()
    if user is None:
        return flask_socketio.disconnect()

    try:
        friend_id = int(data.get("friend_id"))
    except Exception:
        print("[ws][send] bad friend_id", file=sys.stderr, flush=True)
        return

    room = _dm_room(user.user_id, friend_id)
    flask_socketio.join_room(room)
    flask_socketio.emit("type_message", {"sender_id": user.user_id}, room=room)


@socketio.on("send_message")
def ws_send_message(data):
    """
    Send a message to the current friend; broadcast to room.
    data = { "friend_id": int, "body": str }
    """
    user = _require_user()
    print(
        f"[ws][send] user={'NONE' if not user else user.user_id} data={data}",
        file=sys.stderr,
        flush=True,
    )
    if user is None:
        return flask_socketio.disconnect()

    try:
        friend_id = int(data.get("friend_id"))
    except Exception:
        print("[ws][send] bad friend_id", file=sys.stderr, flush=True)
        return
    body = (data.get("body") or "").strip()

    if not body or len(body) > settings.MAX_MESSAGE_LEN:
        print("[ws][send] empty body", file=sys.stderr, flush=True)
        return
    if friend_id == user.user_id or not user.is_friend_with(friend_id):
        print(
            f"[ws][send] not friends or self: friend_id={friend_id}",
            file=sys.stderr,
            flush=True,
        )
        return

    # The user sent a valid message, so we can update the session timer
    # so it doesn't log him out so quickly.
    user.bump_session_timer(settings.SESSION_TIMEOUT)

    # Persist to DB
    with db.create_connection() as conn:
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
    flask_socketio.join_room(room)

    payload = {
        "id": mid,
        "body": body,
        "created_at": created_at.isoformat(),
        "sender_id": user.user_id,
    }

    flask_socketio.emit("message", payload, room=room)
    print(f"[ws][send] emitted to {room}", file=sys.stderr, flush=True)


# ------------------------------------------------------------
# Login/logout
# ------------------------------------------------------------
@app.route("/logout", methods=["GET"])
def logout():
    r = flask.redirect(flask.url_for("login"))
    for cookie in flask.request.cookies:
        r.delete_cookie(cookie)
    return r


@app.route("/login", methods=["GET", "POST"])
def login():
    if flask.request.method == "GET":
        return flask.render_template("login.html")

    email = flask.request.form["email"]
    password = flask.request.form["password"]

    if not email or not password:
        flask.flash("Brakuje jednego z pól", "error")
        return flask.render_template("bad_request.html"), 401

    user = userorm.User(email)
    if not user.user_id or not user.check_password(password):
        flask.flash("Zły e-mail lub hasło", "error")
        return flask.redirect(flask.url_for("login"))

    user.create_session(settings.SESSION_TIMEOUT)
    flask.flash("Witaj {}".format(email), "success")

    r = flask.make_response(flask.redirect(flask.url_for("index")))
    r.set_cookie(
        "token",
        user.get_session_key(),
        httponly=True,
        samesite="Strict",
        secure=True,
    )
    return r


@app.route("/register", methods=["GET", "POST"])
def register():
    if flask.request.method == "GET":
        return flask.render_template("register.html")

    login = flask.request.form["login"]
    email = flask.request.form["email"]
    password = flask.request.form["password"]
    confirm_password = flask.request.form["confirm_password"]

    if not all([login, email, password, confirm_password]):
        flask.flash("Brak wszystkich wymaganych pól", "error")
        return flask.redirect(flask.url_for("register"))

    if password != confirm_password:
        flask.flash("Hasła nie są takie same!", "error")
        return flask.redirect(flask.url_for("register"))

    user = userorm.User(email, login)
    if user.user_id:
        flask.flash("Użytkownik już istnieje.", "error")
        return flask.redirect(flask.url_for("register"))

    user.set_password(password)
    user.save()
    flask.flash("Zarejestrowno pomyślnie!", "success")
    return flask.redirect(flask.url_for("login"))


@app.route("/lib/<path:filename>", methods=["GET"])
def lib(filename):
    return flask.send_from_directory("lib", filename)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    # Enable debug + code reloader inside Docker.
    # NOTE: The reloader watches files in the container filesystem.
    #       Mount your project directory as a volume to get "live" changes.
    socketio.run(
        app,
        host="127.0.0.1",
        port=8080,
        debug=True,  # Flask debug (autoreload)
        use_reloader=True,  # Force reloader for SocketIO server
        allow_unsafe_werkzeug=True,
    )
