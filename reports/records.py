from dataclasses import dataclass

from evidence.pieces import PieceOrigin


@dataclass(frozen=True)
class ReportReceipt:
    report_id: int
    receipt_id: str


@dataclass(frozen=True)
class V1Report:
    report_id: int
    acceptance_id: int
    piece_id: str
    origin: PieceOrigin
    marker: str
    bounds: tuple[int, int]
    receipt: ReportReceipt


def report_from_rows(body, receipt) -> V1Report:
    report_id, acceptance_id, piece_id, batch_id, tray_id, revision_id, marker, lower, upper = body
    receipt_report_id, receipt_id = receipt
    if report_id != receipt_report_id:
        raise ValueError('receipt does not belong to the report body')
    return V1Report(report_id, acceptance_id, piece_id, PieceOrigin(batch_id, tray_id, revision_id),
                    marker, (lower, upper), ReportReceipt(receipt_report_id, receipt_id))
