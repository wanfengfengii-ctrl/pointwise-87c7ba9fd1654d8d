import sqlite3
from uuid import uuid4

from analysis.requests import V1Request
from reports.records import V1Report, report_from_rows
from reports.transactions import report_transaction


def initialize_reports(db: sqlite3.Connection) -> None:
    with report_transaction(db):
        db.execute('''CREATE TABLE IF NOT EXISTS v1_reports (
            report_id INTEGER PRIMARY KEY,
            acceptance_id INTEGER NOT NULL REFERENCES accepted_v1(acceptance_id),
            piece_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            tray_id TEXT NOT NULL,
            revision_id INTEGER NOT NULL,
            marker TEXT NOT NULL,
            lower_rank INTEGER NOT NULL,
            upper_rank INTEGER NOT NULL,
            CHECK (1 <= lower_rank AND lower_rank <= upper_rank)
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS report_receipts (
            report_id INTEGER PRIMARY KEY REFERENCES v1_reports(report_id),
            receipt_id TEXT NOT NULL UNIQUE
        )''')


def publish_v1(db: sqlite3.Connection, request: V1Request) -> V1Report:
    origin = request.origin
    body = (request.acceptance_id, request.piece_id, origin.batch_id, origin.tray_id,
            origin.revision_id, request.marker, *request.bounds)
    receipt_id = uuid4().hex
    with report_transaction(db):
        inserted = db.execute('''INSERT INTO v1_reports (
            acceptance_id, piece_id, batch_id, tray_id, revision_id, marker, lower_rank, upper_rank
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', body)
        report_id = inserted.lastrowid
        db.execute('INSERT INTO report_receipts VALUES (?, ?)', (report_id, receipt_id))
    return report_from_rows((report_id, *body), (report_id, receipt_id))
