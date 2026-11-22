"""Immutable V2 proof reports kept in the centre database.

A stored report is a JSON body whose fields mirror the public dictionary.  The
receipt lives in its own table and is written in the same transaction as the
body, so a reader never observes one without the other.
"""
import json
import sqlite3

from reports.transactions import report_transaction


def initialize_proof_reports(db: sqlite3.Connection) -> None:
    with report_transaction(db):
        db.execute('''CREATE TABLE IF NOT EXISTS proof_reports (
            report_id TEXT PRIMARY KEY NOT NULL,
            acceptance_id TEXT NOT NULL,
            piece_id TEXT NOT NULL,
            body TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS proof_receipts (
            report_id TEXT PRIMARY KEY NOT NULL REFERENCES proof_reports(report_id),
            receipt_id TEXT NOT NULL UNIQUE
        )''')


def build_report(report_id, acceptance_id, piece, marker, side, rank,
                 allowed, status, certificates, receipt_id) -> dict:
    return {
        'report_id': report_id,
        'acceptance_id': acceptance_id,
        'piece_id': piece.piece_id,
        'origin': {
            'batch_id': piece.origin.batch_id,
            'tray_id': piece.origin.tray_id,
            'revision_id': piece.origin.revision_id,
        },
        'marker': marker,
        'side': side,
        'rank': rank,
        'allowed': list(allowed),
        'status': status,
        'certificates': None if certificates is None else list(certificates),
        'receipt': {'report_id': report_id, 'receipt_id': receipt_id},
    }


def insert_report(db: sqlite3.Connection, report: dict) -> None:
    body = {key: value for key, value in report.items() if key != 'receipt'}
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'))
    with report_transaction(db):
        db.execute('INSERT INTO proof_reports (report_id, acceptance_id, piece_id, body) '
                   'VALUES (?, ?, ?, ?)',
                   (report['report_id'], report['acceptance_id'], report['piece_id'], payload))
        db.execute('INSERT INTO proof_receipts (report_id, receipt_id) VALUES (?, ?)',
                   (report['report_id'], report['receipt']['receipt_id']))


def load_report(db: sqlite3.Connection, report_id: str) -> dict:
    row = db.execute('''SELECT body.body, receipt.receipt_id
                        FROM proof_reports AS body
                        JOIN proof_receipts AS receipt ON body.report_id = receipt.report_id
                        WHERE body.report_id = ?''', (report_id,)).fetchone()
    if row is None:
        raise KeyError(report_id)
    payload, receipt_id = row
    report = json.loads(payload)
    report['receipt'] = {'report_id': report['report_id'], 'receipt_id': receipt_id}
    return report
