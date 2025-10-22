# Database setup
# Copyright (c) 2025 Politechnika Wrocławska

from . import settings
import psycopg2


def create_connection():
    return psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASS,
    )
