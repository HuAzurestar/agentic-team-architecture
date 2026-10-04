"""Proposed standalone delivery, record-import and export capability."""

from html import escape


def usable_delivery(delivery):
    return all(delivery.get(key) is True for key in ("qualified", "closed", "same_source"))


def cash_total(records, duplicate_links):
    roots = [record for record in records if not duplicate_links.get(record["id"])]
    return sum(record["amount"] for record in roots)


def import_preview(records):
    rows = []
    for record in records:
        record_id = escape(record["id"], quote=True)
        rows.append(
            f'<tr><td>{record_id}</td><td><input name="source_{record_id}" '
            'aria-label="Source UUID" required value=""></td></tr>'
        )
    return '<form method="post"><table>' + "".join(rows) + '</table><button>Import all</button></form>'


def serialize_row(row):
    return {"id": row["id"], "title": row["title"], "amount": row["amount"]}


def export_package(rows, viewer):
    if any(viewer not in row["allowed"] for row in rows):
        raise PermissionError("restricted row")
    return [serialize_row(row) for row in rows]


def export_single(row, viewer):
    return serialize_row(row)


def download_single(row, viewer):
    return export_single(row, viewer)


def public_summary(row):
    return {"title": row["title"]}
