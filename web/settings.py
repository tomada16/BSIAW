# Project settings
# Copyright (c) 2025 Politechnika Wrocławska
import os

SESSION_TIMEOUT = 600
MAX_MESSAGE_LEN = 2000

DB_HOST = os.environ.get('DB_HOST', 'os')
DB_NAME = os.environ.get('DB_NAME', 'bsiaw')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', '')
