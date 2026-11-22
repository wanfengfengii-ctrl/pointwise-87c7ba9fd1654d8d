import sqlite3

from analysis.rank_review import issue_v1
from bench.revision_store import get_revision
from bench.revisions import record_revision
from evidence.codec import encode_v1
from evidence.intake import accept_v1, read_accepted_v1
from evidence.issued_store import read_issued_v1
from evidence.pieces import PieceOrigin
from evidence.seal import seal_v1
from panel.registry import read_roster
from reports.history import read_v1
from tests.support import LabTestCase, MEMBERS, OVERLAP, emit_scenario


class TestReview(LabTestCase):
    def accept_chain_offline(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        self.source.close()
        receipt = accept_v1(self.center, encode_v1(piece))
        return revision, piece, receipt

    def test_marker_selection(self):
        revision, piece, accepted = self.accept_chain_offline()
        reports = [issue_v1(self.center, accepted.acceptance_id, marker) for marker in ('A', 'B')]
        self.assertEqual([(report.marker, report.bounds) for report in reports],
                         [('A', (1, 2)), ('B', (3, 4))])
        self.assertNotEqual(reports[0].report_id, reports[1].report_id)
        for report in reports:
            self.assertEqual(report.origin, PieceOrigin('batch', 'left', revision.revision_id))
            self.assertEqual(report.piece_id, piece.piece_id)
            self.assertEqual(report.acceptance_id, accepted.acceptance_id)
            self.assertEqual(report.receipt.report_id, report.report_id)
            self.assertEqual(read_v1(self.center, report.report_id), report)

    def test_invalid_request(self):
        _, _, accepted = self.accept_chain_offline()
        with self.assertRaises(KeyError):
            issue_v1(self.center, accepted.acceptance_id + 1, 'B')
        with self.assertRaises(ValueError):
            issue_v1(self.center, accepted.acceptance_id, 'x')
        self.assertEqual(self.report_counts(self.center), (0, 0))

    def test_value_after_correction(self):
        revision, piece, accepted = self.accept_chain_offline()
        issued = issue_v1(self.center, accepted.acceptance_id, 'B')
        self.assertEqual(issued.bounds, (3, 4))
        self.assertEqual(issued.origin, PieceOrigin('batch', 'left', revision.revision_id))
        self.assertEqual(issued.piece_id, piece.piece_id)
        source = self.open_db(self.source_path)
        correction = record_revision(source, 'batch', 'left', OVERLAP)
        self.assertNotEqual(correction.revision_id, revision.revision_id)
        self.assertEqual(seal_v1(source, correction.revision_id).bounds_for('B'), (1, 4))
        source.close()
        self.center.close()
        reopened = self.open_db(self.center_path)
        found = read_v1(reopened, issued.report_id)
        self.assertEqual(found, issued)
        self.assertEqual(found.receipt, issued.receipt)
        emit_scenario('n7', {'marker': 'B', 'piece_id': piece.piece_id,
                             'revision_id': revision.revision_id},
                      (3, 4), issued.bounds,
                      {'bounds': (3, 4), 'piece_id': piece.piece_id,
                       'receipt_id': issued.receipt.receipt_id},
                      {'bounds': found.bounds, 'piece_id': found.piece_id,
                       'receipt_id': found.receipt.receipt_id},
                      ['evidence/intake.py', 'analysis/rank_review.py', 'reports/issue.py',
                       'reports/history.py'],
                      'A and x must precede B in the chosen revision, and y can follow B.')

    def test_fixed_after_reissue(self):
        old_revision, old_piece, old_acceptance = self.accept_chain_offline()
        old = issue_v1(self.center, old_acceptance.acceptance_id, 'B')
        source = self.open_db(self.source_path)
        revision = record_revision(source, 'batch', 'left', OVERLAP, [('A', 'x')])
        piece = seal_v1(source, revision.revision_id)
        source.close()
        acceptance = accept_v1(self.center, encode_v1(piece))
        new = issue_v1(self.center, acceptance.acceptance_id, 'B')
        self.center.close()
        reopened = self.open_db(self.center_path)
        for report, expected_piece, expected_revision, bounds in [
            (old, old_piece, old_revision, (3, 4)), (new, piece, revision, (1, 4)),
        ]:
            saved = read_v1(reopened, report.report_id)
            self.assertEqual(saved, report)
            self.assertEqual(saved.piece_id, expected_piece.piece_id)
            self.assertEqual(saved.origin.revision_id, expected_revision.revision_id)
            self.assertEqual(saved.bounds, bounds)
            self.assertEqual(saved.marker, 'B')
        self.assertNotEqual(old.receipt, new.receipt)
        self.assertEqual(self.report_counts(reopened), (2, 2))

    def test_reinitialize(self):
        first = self.record_chain()
        second = record_revision(self.source, 'batch', 'left', OVERLAP)
        piece = seal_v1(self.source, first.revision_id)
        second_piece = seal_v1(self.source, second.revision_id)
        self.source.close()
        receipt = accept_v1(self.center, encode_v1(piece))
        second_receipt = accept_v1(self.center, encode_v1(second_piece))
        report = issue_v1(self.center, receipt.acceptance_id, 'B')
        self.center.close()
        source = self.open_db(self.source_path)
        center = self.open_db(self.center_path)
        self.initialize_source(source)
        self.initialize_center(center)
        self.assertEqual(read_roster(source, 'batch', 'left').members, MEMBERS)
        self.assertEqual(get_revision(source, first.revision_id), first)
        self.assertEqual(get_revision(source, second.revision_id), second)
        self.assertEqual(read_issued_v1(source, piece.piece_id), piece)
        self.assertEqual(read_issued_v1(source, second_piece.piece_id), second_piece)
        self.assertEqual(read_accepted_v1(center, receipt.acceptance_id), (piece, receipt))
        self.assertEqual(read_accepted_v1(center, second_receipt.acceptance_id),
                         (second_piece, second_receipt))
        self.assertEqual(accept_v1(center, encode_v1(piece)), receipt)
        self.assertEqual(read_v1(center, report.report_id), report)
        self.assertEqual(self.report_counts(center), (1, 1))

    def test_unknown_report(self):
        _, _, accepted = self.accept_chain_offline()
        report = issue_v1(self.center, accepted.acceptance_id, 'B')
        with self.assertRaises(KeyError):
            read_v1(self.center, report.report_id + 1)

    def test_failed_commit_retry(self):
        _, piece, accepted = self.accept_chain_offline()
        self.center.executescript('''CREATE TRIGGER test_receipt_unavailable
            BEFORE INSERT ON report_receipts
            WHEN EXISTS (SELECT 1 FROM v1_reports WHERE report_id = NEW.report_id)
            BEGIN
                SELECT RAISE(ABORT, 'receipt unavailable after body');
            END;
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt unavailable after body'):
            issue_v1(self.center, accepted.acceptance_id, 'B')
        self.assertEqual(self.report_counts(self.center), (0, 0))
        self.assertEqual(read_accepted_v1(self.center, accepted.acceptance_id), (piece, accepted))
        self.center.execute('DROP TRIGGER test_receipt_unavailable')
        report = issue_v1(self.center, accepted.acceptance_id, 'B')
        self.assertEqual(self.report_counts(self.center), (1, 1))
        self.assertEqual(report.bounds, (3, 4))
        self.assertEqual(read_v1(self.center, report.report_id), report)

    def test_durable_rollback(self):
        _, piece, accepted = self.accept_chain_offline()
        prior = issue_v1(self.center, accepted.acceptance_id, 'A')
        self.defer_commit_failure(self.center, 'report_receipts')
        observer = self.open_db(self.center_path)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            issue_v1(self.center, accepted.acceptance_id, 'B')
        self.assertFalse(self.center.in_transaction)
        self.assertEqual(self.report_counts(observer), (1, 1))
        self.assertEqual(self.count(observer, 'test_commit_gate'), 0)
        observer.close()
        self.center.close()
        reopened = self.open_db(self.center_path)
        self.assertEqual(self.report_counts(reopened), (1, 1))
        self.assertEqual(read_v1(reopened, prior.report_id), prior)
        self.assertEqual(read_accepted_v1(reopened, accepted.acceptance_id), (piece, accepted))
        with self.assertRaises(KeyError):
            read_v1(reopened, prior.report_id + 1)
        reopened.execute('DROP TRIGGER test_fail_commit')
        retry = issue_v1(reopened, accepted.acceptance_id, 'B')
        self.assertEqual(self.report_counts(reopened), (2, 2))
        self.assertEqual((retry.piece_id, retry.origin, retry.bounds),
                         (piece.piece_id, piece.origin, (3, 4)))
        self.assertEqual(read_v1(reopened, retry.report_id), retry)
