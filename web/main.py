#!/usr/bin/env python3

import flask

app = flask.Flask(__name__)


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