# Project settings
# Copyright (c) 2025 Politechnika Wrocławska

import json
import os


SESSION_TIMEOUT = 600
MAX_MESSAGE_LEN = 2000

DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "bsiaw")

db_credentials = os.environ.get("DB_CREDENTIALS", None)
if not db_credentials:
    print("error: missing DB_CREDENTIALS env variable")
    exit(1)

db_credentials = json.loads(db_credentials)
if "password" not in db_credentials or "username" not in db_credentials:
    print(
        "error: DB_CREDENTIALS should be a JSON blob with password & username fields"
    )
    exit(1)

DB_USER = db_credentials["username"]
DB_PASS = db_credentials["password"]
