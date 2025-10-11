#!/usr/bin/env python3

import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return "<p>witaj na mojej strone!!11!</p>"
