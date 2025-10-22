# Database setup
# Copyright (c) 2025 Politechnika Wrocławska

import psycopg2


def create_connection():
    return psycopg2.connect(
        host="localhost", database="bsiaw", user="postgres", password=""
    )
