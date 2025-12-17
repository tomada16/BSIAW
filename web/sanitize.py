# Input data validators
# Copyright (c) 2025 Politechnika Wrocławska

import re


def login(s):
    pattern = r"^[a-zA-Z0-9_]+$"
    return s if s and re.match(pattern, s) else None


def email(s):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return s if s and re.match(pattern, s) else None


def password(s):
    pattern = r"^[^ ]+$"
    return s if s and re.match(pattern, s) else None
