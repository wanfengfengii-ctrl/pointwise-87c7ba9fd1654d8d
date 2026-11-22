import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bench.revision_store import initialize_revisions
from bench.revisions import record_revision
from evidence.intake import initialize_intake
from evidence.issued_store import initialize_issued_pieces
from panel.registry import initialize_panel, register_panel
from reports.issue import initialize_reports


MEMBERS = ('A', 'B', 'x', 'y')
OVERLAP = tuple((member, 0, 1) for member in MEMBERS)
CHAIN = (('A', 'x'), ('x', 'B'))


def emit_scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual,
                  code_paths, oracle):
    evidence = {
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }
    print('POINTWISE_SCENARIO ' + json.dumps(evidence, ensure_ascii=False, sort_keys=True))


class LabTestCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source_path = Path(temporary.name) / 'source.sqlite3'
        self.center_path = Path(temporary.name) / 'center.sqlite3'
        self.source = self.open_db(self.source_path)
        self.center = self.open_db(self.center_path)
        self.initialize_source(self.source)
        self.initialize_center(self.center)

    def open_db(self, path):
        db = sqlite3.connect(path)
        self.addCleanup(db.close)
        db.execute('PRAGMA foreign_keys = ON')
        return db

    @staticmethod
    def initialize_source(db):
        initialize_panel(db)
        initialize_revisions(db)
        initialize_issued_pieces(db)

    @staticmethod
    def initialize_center(db):
        initialize_intake(db)
        initialize_reports(db)

    def register(self, tray='left', members=MEMBERS):
        return register_panel(self.source, 'batch', ('A', 'B'), 'MPa', tray, members)

    def record_chain(self):
        self.register()
        return record_revision(self.source, 'batch', 'left', OVERLAP, CHAIN)

    def count(self, db, table):
        allowed = {'panel_batches', 'panel_trays', 'bench_revisions', 'issued_v1',
                   'accepted_v1', 'v1_reports', 'report_receipts', 'test_commit_gate'}
        self.assertIn(table, allowed)
        return db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]

    def report_counts(self, db):
        return self.count(db, 'v1_reports'), self.count(db, 'report_receipts')

    def defer_commit_failure(self, db, table):
        self.assertIn(table, {'issued_v1', 'report_receipts'})
        db.executescript(f'''
            CREATE TABLE test_commit_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE test_commit_gate (
                parent_id INTEGER REFERENCES test_commit_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER test_fail_commit AFTER INSERT ON {table}
            BEGIN
                INSERT INTO test_commit_gate (parent_id) VALUES (1);
            END;
        ''')
