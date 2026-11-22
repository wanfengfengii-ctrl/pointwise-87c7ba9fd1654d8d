import json
import sqlite3
from fractions import Fraction
from itertools import permutations

from bench.revisions import record_revision
from evidence.codec import decode_v1, encode_v1
from evidence.intake import accept_v1, read_accepted_v1
from evidence.issued_store import read_issued_v1
from evidence.pieces import PieceOrigin
from evidence.seal import seal_v1
from tests.support import CHAIN, MEMBERS, OVERLAP, LabTestCase, emit_scenario


class TestEvidence(LabTestCase):
    def test_closed_touch(self):
        self.register(members=('A', 'B', 'x'))
        revision = record_revision(self.source, 'batch', 'left',
                                   [('A', 0, 1), ('B', 0, 2), ('x', 1, 2)])
        self.assertEqual(revision.graph.edges, ())
        piece = seal_v1(self.source, revision.revision_id)
        self.assertEqual(piece.rank_bounds, {'A': (1, 3), 'B': (1, 3)})

    def test_exact_endpoints(self):
        self.register()
        rows = [('A', 0, '1/3'), ('B', 0, 1), ('x', 0, '2/3'), ('y', '2/6', 1)]
        revision = record_revision(self.source, 'batch', 'left', rows, CHAIN)
        readings = dict(revision.readings)
        self.assertEqual(readings['A'].upper, Fraction(1, 3))
        self.assertEqual(readings['y'].lower, readings['A'].upper)
        self.assertEqual(revision.graph.inferred_edges, ())
        text = encode_v1(seal_v1(self.source, revision.revision_id))
        self.source.close()
        receipt = accept_v1(self.center, text)
        accepted, _ = read_accepted_v1(self.center, receipt.acceptance_id)
        self.assertEqual(accepted.rank_bounds, {'A': (1, 2), 'B': (3, 4)})

    def test_offline_repeat(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        text = encode_v1(piece)
        self.source.close()
        receipt = accept_v1(self.center, text)
        self.assertEqual(accept_v1(self.center, text), receipt)
        stored, repeated_receipt = read_accepted_v1(self.center, receipt.acceptance_id)
        expected = {'A': (1, 2), 'B': (3, 4)}
        self.assertEqual(piece.rank_bounds, expected)
        self.assertEqual(stored.rank_bounds, expected)
        self.assertEqual(stored, piece)
        self.assertEqual(repeated_receipt, receipt)
        self.assertEqual(receipt.origin, PieceOrigin('batch', 'left', revision.revision_id))
        self.assertEqual(self.count(self.center, 'accepted_v1'), 1)
        emit_scenario('n5', {'members': MEMBERS, 'readings': OVERLAP, 'certificates': CHAIN},
                      expected, piece.rank_bounds,
                      {'bounds': expected, 'piece_id': piece.piece_id, 'count': 1},
                      {'bounds': stored.rank_bounds, 'piece_id': repeated_receipt.piece_id,
                       'count': self.count(self.center, 'accepted_v1')},
                      ['bench/revisions.py', 'analysis/closure.py', 'analysis/rank_bounds.py',
                       'evidence/seal.py', 'evidence/intake.py'],
                      'Insert y at each of the four positions around the chain A, x, B.')

    def test_transitive_bounds(self):
        revision = self.record_chain()
        self.assertEqual(revision.graph.inferred_edges, ())
        self.assertEqual(revision.graph.edges, CHAIN)
        piece = seal_v1(self.source, revision.revision_id)
        self.source.close()
        receipt = accept_v1(self.center, encode_v1(piece))
        stored, _ = read_accepted_v1(self.center, receipt.acceptance_id)
        orders = [order for order in permutations(MEMBERS)
                  if order.index('A') < order.index('x') < order.index('B')]
        self.assertEqual(len(orders), 4)
        reachable = {marker: {order.index(marker) + 1 for order in orders} for marker in ('A', 'B')}
        self.assertEqual(reachable, {'A': {1, 2}, 'B': {3, 4}})
        for marker, (lower, upper) in stored.rank_bounds.items():
            self.assertEqual(set(range(lower, upper + 1)), reachable[marker])

    def test_revision_pin(self):
        old = self.record_chain()
        new = record_revision(self.source, 'batch', 'left', OVERLAP, [('A', 'x')])
        old_piece = seal_v1(self.source, old.revision_id)
        new_piece = seal_v1(self.source, new.revision_id)
        self.assertNotEqual(old.revision_id, new.revision_id)
        self.assertNotEqual(old_piece.piece_id, new_piece.piece_id)
        self.assertEqual(read_issued_v1(self.source, old_piece.piece_id), old_piece)
        self.source.close()
        for piece, revision, expected in [
            (old_piece, old, {'A': (1, 2), 'B': (3, 4)}),
            (new_piece, new, {'A': (1, 3), 'B': (1, 4)}),
        ]:
            receipt = accept_v1(self.center, encode_v1(piece))
            accepted, _ = read_accepted_v1(self.center, receipt.acceptance_id)
            self.assertEqual(receipt.origin.revision_id, revision.revision_id)
            self.assertEqual(receipt.piece_id, piece.piece_id)
            self.assertEqual(accepted.rank_bounds, expected)

    def test_unknown_revision(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        with self.assertRaises(KeyError):
            seal_v1(self.source, revision.revision_id + 1)
        self.assertEqual(self.count(self.source, 'issued_v1'), 1)
        self.assertEqual(read_issued_v1(self.source, piece.piece_id), piece)

    def test_v1_projection(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        text = encode_v1(piece)
        expected = {
            'version': 1, 'piece_id': piece.piece_id, 'batch_id': 'batch', 'tray_id': 'left',
            'revision_id': revision.revision_id, 'markers': ['A', 'B'], 'specimen_count': 4,
            'rank_bounds': {'A': [1, 2], 'B': [3, 4]},
        }
        self.assertEqual(json.loads(text), expected)
        self.assertEqual(decode_v1(text), piece)
        self.source.close()
        receipt = accept_v1(self.center, text)
        stored, _ = read_accepted_v1(self.center, receipt.acceptance_id)
        self.assertEqual(json.loads(encode_v1(stored)), expected)
        self.assertEqual(stored.bounds_for('B'), (3, 4))

    def test_seal_rollback(self):
        revision = self.record_chain()
        self.defer_commit_failure(self.source, 'issued_v1')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            seal_v1(self.source, revision.revision_id)
        self.assertFalse(self.source.in_transaction)
        with self.subTest(connection='independent'):
            observer = self.open_db(self.source_path)
            self.assertEqual(self.count(observer, 'issued_v1'), 0)
            self.assertEqual(self.count(observer, 'test_commit_gate'), 0)
        self.source.execute('DROP TRIGGER test_fail_commit')
        piece = seal_v1(self.source, revision.revision_id)
        self.assertEqual(self.count(observer, 'issued_v1'), 1)
        self.assertEqual(read_issued_v1(observer, piece.piece_id), piece)

    def test_equivalent_encoding(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        original = encode_v1(piece)
        parsed = json.loads(original)
        parsed['rank_bounds'] = dict(reversed(list(parsed['rank_bounds'].items())))
        alternate = json.dumps(dict(reversed(list(parsed.items()))), indent=2)
        self.assertNotEqual(original, alternate)
        self.source.close()
        first = accept_v1(self.center, original)
        self.assertEqual(accept_v1(self.center, alternate), first)
        self.assertEqual(read_accepted_v1(self.center, first.acceptance_id), (piece, first))
        self.assertEqual(self.count(self.center, 'accepted_v1'), 1)

    def test_conflicting_repeat(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        text = encode_v1(piece)
        self.source.close()
        first = accept_v1(self.center, text)
        conflict = json.loads(text)
        conflict['rank_bounds']['A'] = [1, 3]
        self.assertEqual(decode_v1(json.dumps(conflict)).bounds_for('A'), (1, 3))
        with self.assertRaises(ValueError):
            accept_v1(self.center, json.dumps(conflict))
        self.assertEqual(self.count(self.center, 'accepted_v1'), 1)
        self.assertEqual(read_accepted_v1(self.center, first.acceptance_id), (piece, first))

    def test_invalid_bounds(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        text = encode_v1(piece)
        self.source.close()
        first = accept_v1(self.center, text)
        for index, bounds in enumerate(([0, 2], [3, 5], [3, 2], [True, 2])):
            invalid = json.loads(text)
            invalid['piece_id'] = f'unseen-{index}'
            invalid['rank_bounds']['A'] = bounds
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                accept_v1(self.center, json.dumps(invalid))
        self.assertEqual(self.count(self.center, 'accepted_v1'), 1)
        self.assertEqual(read_accepted_v1(self.center, first.acceptance_id), (piece, first))

    def test_invalid_format(self):
        revision = self.record_chain()
        piece = seal_v1(self.source, revision.revision_id)
        text = encode_v1(piece)
        self.source.close()
        first = accept_v1(self.center, text)
        invalid_cases = [dict(version=2), dict(version=True), dict(rank_bounds={'A': [1, 2]}),
                         dict(specimen_count='4'), dict(markers=['A', 'A']),
                         dict(tray_id=[]), dict(revision_id=False), dict(extra=[])]
        for index, patch in enumerate(invalid_cases):
            body = json.loads(text)
            body.update({'piece_id': f'unseen-format-{index}', **patch})
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                accept_v1(self.center, json.dumps(body))
        with self.assertRaises(ValueError):
            accept_v1(self.center, text.replace('"A":[1,2]', '"A":[1,2],"A":[1,2]'))
        with self.assertRaises(ValueError):
            accept_v1(self.center, text[:-1])
        self.assertEqual(self.count(self.center, 'accepted_v1'), 1)
        self.assertEqual(read_accepted_v1(self.center, first.acceptance_id), (piece, first))
