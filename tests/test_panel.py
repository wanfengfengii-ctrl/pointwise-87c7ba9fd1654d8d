from fractions import Fraction

from bench.observations import ReadingInterval
from bench.revision_store import get_revision
from bench.revisions import record_revision
from panel.registry import read_roster, register_panel
from tests.support import LabTestCase, MEMBERS, OVERLAP


class TestPanel(LabTestCase):
    def test_initial_revision(self):
        self.assertEqual(self.register(), ('batch', 'left'))
        rows = [('A', 0, '1/3'), ('x', '1/2', '2/3'), ('B', 1, 1), ('y', 0, 1)]
        revision = record_revision(self.source, 'batch', 'left', rows, [('A', 'x')])
        saved = get_revision(self.source, revision.revision_id)
        self.assertEqual(saved, revision)
        self.assertEqual(saved.roster.batch.unit, 'MPa')
        self.assertEqual(saved.roster.members, MEMBERS)
        self.assertEqual(dict(saved.readings), {
            'A': ReadingInterval(Fraction(0), Fraction(1, 3)),
            'B': ReadingInterval(Fraction(1), Fraction(1)),
            'x': ReadingInterval(Fraction(1, 2), Fraction(2, 3)),
            'y': ReadingInterval(Fraction(0), Fraction(1)),
        })
        self.assertEqual(set(saved.graph.vertices), set(MEMBERS))
        self.assertEqual(set(saved.graph.inferred_edges), {('A', 'x'), ('A', 'B'), ('x', 'B')})
        self.assertEqual(saved.graph.certified_edges, (('A', 'x'),))
        self.assertEqual(len(saved.graph.edges), 3)

    def test_shared_roster(self):
        self.register()
        self.assertEqual(register_panel(self.source, 'batch', ['B', 'A'], 'MPa', 'right',
                                        ['x', 'B', 'A']), ('batch', 'right'))
        left = read_roster(self.source, 'batch', 'left')
        right = read_roster(self.source, 'batch', 'right')
        self.assertEqual(left.batch, right.batch)
        self.assertEqual(left.batch.markers.as_tuple(), ('A', 'B'))
        self.assertIn('x', left.members)
        self.assertEqual(right.members, ('A', 'B', 'x'))
        self.assertNotEqual(left.tray_id, right.tray_id)
        self.assertEqual(self.count(self.source, 'panel_batches'), 1)
        self.assertEqual(self.count(self.source, 'panel_trays'), 2)
        self.assertEqual(self.register(members=list(reversed(MEMBERS))), ('batch', 'left'))
        left_revision = record_revision(self.source, 'batch', 'left', OVERLAP)
        right_revision = record_revision(self.source, 'batch', 'right',
                                         [('A', 0, 1), ('B', 0, 1), ('x', 2, 2)])
        self.assertEqual(dict(left_revision.readings)['x'].upper, 1)
        self.assertEqual(dict(right_revision.readings)['x'].upper, 2)

    def test_duplicate_local_id(self):
        with self.assertRaises(ValueError):
            self.register(members=('A', 'B', 'x', 'x'))
        self.assertEqual(self.count(self.source, 'panel_batches'), 0)
        self.assertEqual(self.count(self.source, 'panel_trays'), 0)
        with self.assertRaises(KeyError):
            read_roster(self.source, 'batch', 'left')
        self.assertEqual(self.register(), ('batch', 'left'))
        self.assertEqual(read_roster(self.source, 'batch', 'left').members, MEMBERS)

    def test_batch_definition(self):
        self.register()
        original = read_roster(self.source, 'batch', 'left')
        with self.assertRaises(ValueError):
            register_panel(self.source, 'batch', ('A', 'B'), 'kPa', 'right', MEMBERS)
        with self.assertRaises(ValueError):
            register_panel(self.source, 'batch', ('A', 'C'), 'MPa', 'right', ('A', 'C', 'x'))
        with self.assertRaises(ValueError):
            self.register(members=('A', 'B', 'x'))
        self.assertEqual(self.count(self.source, 'panel_batches'), 1)
        self.assertEqual(self.count(self.source, 'panel_trays'), 1)
        self.assertEqual(read_roster(self.source, 'batch', 'left'), original)
        with self.assertRaises(KeyError):
            read_roster(self.source, 'batch', 'right')

    def test_missing_or_equal_markers(self):
        with self.assertRaises(ValueError):
            self.register(members=('A', 'x', 'y'))
        with self.assertRaises(ValueError):
            register_panel(self.source, 'batch', ('A', 'A'), 'MPa', 'left', MEMBERS)
        self.assertEqual(self.count(self.source, 'panel_batches'), 0)
