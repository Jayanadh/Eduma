"""Keeps tokens out of logs (TST-021): Django logs the path of every refused or failed request, and a document
verification link carries its token in the path."""

import logging
import re

TOKEN_IN_PATH = re.compile(r"(/public/verify/)[^/\s?\"']+")


def _redact(value):
    return TOKEN_IN_PATH.sub(r"\1[redacted]", value) if isinstance(value, str) else value


class RedactTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) for a in record.args)
        return True
