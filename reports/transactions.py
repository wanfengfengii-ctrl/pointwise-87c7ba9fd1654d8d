import sqlite3
from contextlib import contextmanager


@contextmanager
def write_transaction(db: sqlite3.Connection):
    """Own a complete write transaction, including failure at commit."""
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


report_transaction = write_transaction
