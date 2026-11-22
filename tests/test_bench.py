from fractions import Fraction

from bench.revision_store import get_revision
from bench.revisions import record_revision
from evidence.seal import seal_v1
from tests.support import CHAIN, OVERLAP, LabTestCase


class TestBench(LabTestCase):
    def test_reading_coverage(self):
        initial = self.record_chain()
        self.register(tray='right', members=('A', 'B', 'foreign'))
        malformed = [OVERLAP[:-1], OVERLAP + (('x', 0, 1),),
                     OVERLAP[:-1] + (('foreign', 0, 1),)]
        for rows in malformed:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                record_revision(self.source, 'batch', 'left', rows)
        self.assertEqual(self.count(self.source, 'bench_revisions'), 1)
        self.assertEqual(get_revision(self.source, initial.revision_id), initial)
        self.assertEqual(len(initial.readings), 4)

    def test_invalid_reading(self):
        self.register()
        bad_rows = [('y', 2, 1), ('y', 0), ('y', None, 1), ('y', 'bad', 1),
                    ('y', '1/0', 1), ('y', True, 1), ('y', 0.5, 1)]
        for reading in bad_rows:
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                record_revision(self.source, 'batch', 'left', (*OVERLAP[:-1], reading))
        with self.assertRaises(KeyError):
            record_revision(self.source, 'batch', 'missing', OVERLAP)
        self.assertEqual(self.count(self.source, 'bench_revisions'), 0)

    def test_exact_decimal_and_fraction(self):
        self.register()
        rows = [('A', '0.125', Fraction(3, 8)), *OVERLAP[1:]]
        revision = record_revision(self.source, 'batch', 'left', rows)
        self.assertEqual(get_revision(self.source, revision.revision_id), revision)
        stored = dict(revision.readings)['A']
        self.assertEqual((stored.lower, stored.upper), (Fraction(1, 8), Fraction(3, 8)))

    def test_reverse_certificate(self):
        initial = self.record_chain()
        correction = [('A', 0, 0), ('B', 0, 2), ('x', 1, 1), ('y', 0, 2)]
        with self.assertRaisesRegex(ValueError, 'cycle'):
            record_revision(self.source, 'batch', 'left', correction, [('x', 'A')])
        self.assertEqual(self.count(self.source, 'bench_revisions'), 1)
        saved = get_revision(self.source, initial.revision_id)
        self.assertEqual(saved, initial)
        self.assertEqual(saved.graph.certified_edges, CHAIN)
        old_piece = seal_v1(self.source, initial.revision_id)
        self.assertEqual(old_piece.origin.revision_id, initial.revision_id)
        self.assertEqual(old_piece.rank_bounds, {'A': (1, 2), 'B': (3, 4)})

    def test_certificate_validation_and_deduplication(self):
        self.register()
        for certificates in [(('x', 'x'),), (('x', 'outside'),), (('x',),),
                             (('A', 'x'), ('x', 'B'), ('B', 'A'))]:
            with self.subTest(certificates=certificates), self.assertRaises(ValueError):
                record_revision(self.source, 'batch', 'left', OVERLAP, certificates)
        self.assertEqual(self.count(self.source, 'bench_revisions'), 0)
        snapshot = record_revision(self.source, 'batch', 'left', OVERLAP, (*CHAIN, CHAIN[0]))
        self.assertEqual(snapshot.graph.inferred_edges, ())
        self.assertEqual(snapshot.graph.certified_edges, CHAIN)
        self.assertEqual(snapshot.graph.edges, CHAIN)
