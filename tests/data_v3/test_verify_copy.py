from data_platform.v3.verify_copy import Signature


def test_row_signature_is_independent_of_scan_order_and_counts_duplicates():
    rows = ["0" * 31 + "1", "0" * 31 + "2", "0" * 31 + "1"]
    forward = Signature()
    reverse = Signature()
    for digest in rows:
        forward = forward.add(digest)
    for digest in reversed(rows):
        reverse = reverse.add(digest)
    assert forward == reverse
    assert forward.count == 3
    assert forward != Signature().add(rows[0]).add(rows[1])
