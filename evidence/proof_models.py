"""V2 proof pieces: self-contained offline evidence for rank thresholds.

The V2 handoff keeps the two named batch markers but replaces every ordinary
specimen by a piece-local label, so original specimen numbers never leave the
source database.  The original readings are represented only by the strict
precedence they imply.  Manual certificates travel as identifiers that are
valid only on their own piece, so an independently issued piece never shares
them.
"""
from collections.abc import Mapping
from dataclasses import dataclass

from bench.consistency import topological_order
from bench.precedence import PrecedenceGraph
from evidence.pieces import PieceOrigin
from panel.markers import MarkerPair, make_marker_pair, validate_identifier


def _label(value, what: str) -> str:
    try:
        return validate_identifier(value)
    except ValueError as exc:
        raise ValueError(f'{what} must be nonblank printable text') from exc


def _label_sequence(value, what: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, (tuple, list)):
        raise ValueError(f'{what} must be a sequence of identifiers')
    return tuple(_label(item, what) for item in value)


def _edge(value, specimens: frozenset) -> tuple[str, str]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError('a precedence edge requires two specimen labels')
    earlier = _label(value[0], 'precedence endpoint')
    later = _label(value[1], 'precedence endpoint')
    if earlier == later:
        raise ValueError('a precedence edge cannot join a specimen to itself')
    if earlier not in specimens or later not in specimens:
        raise ValueError('a precedence edge references an unknown specimen')
    return earlier, later


def _inferred_edges(value, specimens: frozenset) -> tuple[tuple[str, str], ...]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, (tuple, list)):
        raise ValueError('inferred precedence must be a sequence of edges')
    return tuple(sorted({_edge(edge, specimens) for edge in value}))


def _marker_nodes(value, markers: MarkerPair, specimens: frozenset) -> tuple[tuple[str, str], ...]:
    if isinstance(value, Mapping):
        items = list(value.items())
    elif isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ValueError('marker nodes must map the named markers to specimens')
    else:
        items = []
        for item in value:
            if isinstance(item, (str, bytes, Mapping)) or not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError('a marker node requires a marker and a specimen label')
            items.append((item[0], item[1]))
    mapping = {}
    for name, label in items:
        name = _label(name, 'marker node')
        label = _label(label, 'marker node')
        if name in mapping:
            raise ValueError('duplicate marker node')
        mapping[name] = label
    if set(mapping) != set(markers.as_tuple()):
        raise ValueError('marker nodes must cover exactly the two named markers')
    labels = list(mapping.values())
    if len(set(labels)) != len(labels):
        raise ValueError('the two markers must map to distinct specimens')
    if not specimens.issuperset(labels):
        raise ValueError('a marker node is outside the specimen set')
    return tuple(sorted(mapping.items()))


def _certificate_edges(value, certificate_ids, specimens: frozenset):
    if isinstance(value, Mapping):
        items = list(value.items())
    elif isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ValueError('certificate edges must be keyed by certificate identifier')
    else:
        items = []
        for item in value:
            if isinstance(item, (str, bytes, Mapping)) or not isinstance(item, (tuple, list)) or len(item) != 3:
                raise ValueError('a certificate edge requires an identifier and two specimens')
            items.append((item[0], (item[1], item[2])))
    mapping = {}
    for cid, edge in items:
        cid = _label(cid, 'certificate identifier')
        if cid in mapping:
            raise ValueError('duplicate certificate identifier')
        mapping[cid] = _edge(edge, specimens)
    if set(mapping) != set(certificate_ids):
        raise ValueError('certificate edges must match the certificate identifiers')
    return tuple((cid, mapping[cid][0], mapping[cid][1]) for cid in sorted(mapping))


@dataclass(frozen=True)
class ProofPiece:
    piece_id: str
    origin: PieceOrigin
    markers: MarkerPair
    specimen_count: int
    certificate_ids: tuple[str, ...]
    specimens: tuple[str, ...]
    marker_nodes: tuple[tuple[str, str], ...]
    inferred_edges: tuple[tuple[str, str], ...]
    certificate_edges: tuple[tuple[str, str, str], ...]

    @property
    def marker_choices(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.marker_nodes)

    def node_for(self, marker: str) -> str:
        for name, label in self.marker_nodes:
            if name == marker:
                return label
        raise ValueError('marker is not present on this piece')

    def certificate_edge(self, certificate_id: str) -> tuple[str, str]:
        for cid, earlier, later in self.certificate_edges:
            if cid == certificate_id:
                return earlier, later
        raise ValueError('certificate identifier is not present on this piece')

    def certificate_map(self) -> dict[str, tuple[str, str]]:
        return {cid: (earlier, later) for cid, earlier, later in self.certificate_edges}


def make_proof_piece(piece_id, origin, markers, specimen_count, certificate_ids,
                     specimens, marker_nodes, inferred_edges,
                     certificate_edges) -> ProofPiece:
    piece_id = _label(piece_id, 'piece identity')
    if not isinstance(origin, PieceOrigin):
        raise ValueError('a V2 piece requires a piece origin')
    pair = make_marker_pair(markers)
    if type(specimen_count) is not int or specimen_count < 2:
        raise ValueError('specimen_count must be an integer of at least two')

    specimen_labels = _label_sequence(specimens, 'specimens')
    if len(set(specimen_labels)) != len(specimen_labels):
        raise ValueError('specimen labels must be distinct')
    if len(specimen_labels) != specimen_count:
        raise ValueError('specimen_count must match the number of specimens')
    specimen_set = frozenset(specimen_labels)

    certificate_ids = _label_sequence(certificate_ids, 'certificate identifiers')
    if len(set(certificate_ids)) != len(certificate_ids):
        raise ValueError('certificate identifiers must be distinct')
    certificate_ids = tuple(sorted(certificate_ids))

    nodes = _marker_nodes(marker_nodes, pair, specimen_set)
    inferred = _inferred_edges(inferred_edges, specimen_set)
    certificates = _certificate_edges(certificate_edges, certificate_ids, specimen_set)

    graph = PrecedenceGraph(tuple(sorted(specimen_set)), inferred,
                            tuple((earlier, later) for _, earlier, later in certificates))
    topological_order(graph)

    return ProofPiece(piece_id, origin, pair, specimen_count, certificate_ids,
                      tuple(sorted(specimen_set)), nodes, inferred, certificates)


def local_specimen_labels(members, markers) -> dict[str, str]:
    """Map original specimen identities to piece-local labels.

    Named batch markers keep their identity so the offline reviewer can pick a
    marker.  Every ordinary specimen gets a fresh label that can never collide
    with an original identity on the tray.
    """
    marker_names = set(markers.as_tuple())
    used = set(members)
    labels = {name: name for name in markers.as_tuple()}
    counter = 1
    for member in sorted(members):
        if member in marker_names:
            continue
        while True:
            candidate = f's{counter}'
            counter += 1
            if candidate not in used and candidate not in labels.values():
                break
        labels[member] = candidate
    return labels
