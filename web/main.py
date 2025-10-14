#!/usr/bin/env python3
import hashlib
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2


app = Flask(__name__)
# Temporary will be changed when sesions are done | "secret" will be later deleted
app.secret_key = "secret"

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="bsiaw",
    user="postgres",
    password=""
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE email=%s", (email,))
        database_hash = cur.fetchone()
        cur.close()

        #TODO check password if it matches then good
        if database_hash and database_hash[0] == password_hash:
            flash("Welcome {}".format(email), "success")
            return redirect(url_for("index"))
        else:
            flash("Zły e-mail lub hasło", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Hasła nie są takie same!", "error")
            return redirect(url_for("register"))
        
        #TODO hash passowrd
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, password_hash))
            conn.commit()
            flash("Zarejestrowano pomyślnie!", "success")
            return redirect(url_for("login"))
        except Exception as e:
            conn.rollback()
            flash("Ten email już istnieje lub wystąpił błąd przy rejestracji.", "error")
        finally:
            cur.close()

    return render_template("register.html")
