#!/usr/bin/env python3
import os

from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")

app = Flask(__name__)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        password_hash = "TODO"

        #TODO change query according to database
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        #TODO check password if it matches then good
        if user and True:
            flash("Welcome {}".format(email), "success")
            return redirect(url_for("index"))
        else:
            flash("Wrong email or password", "error")

    return render_template("login.html")


@app.route("/register")
def register():
    return render_template("register.html")