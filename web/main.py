#!/usr/bin/env python3
import os

import flask
import psycopg2
from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")

app = flask.Flask(__name__)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/login")
def login():
    return flask.render_template("login.html")

@app.route("/register")
def register():
    return flask.render_template("register.html")

# Need to run from IDE
if __name__ == "__main__":
    app.run(debug=True)