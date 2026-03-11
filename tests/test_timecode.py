from youtube2datasets.timecode import format_timecode, is_in_ranges, parse_time_range, parse_timecode


def test_parse_timecode_accepts_seconds_and_hms() -> None:
    assert parse_timecode("12.5") == 12.5
    assert parse_timecode("01:02:03.5") == 3723.5
    assert parse_timecode("02:03") == 123.0


def test_format_timecode_round_trip() -> None:
    assert format_timecode(3723.5) == "01:02:03.500"


def test_parse_range_and_membership() -> None:
    item = parse_time_range("00:00:10-00:00:15")
    assert item.start == 10
    assert item.end == 15
    assert is_in_ranges(10.0, [item])
    assert not is_in_ranges(15.0, [item])
