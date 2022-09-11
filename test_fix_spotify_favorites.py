from pathlib import Path

import pytest

import fix_spotify_favorites as fix


def test_Track_from_result():
    data = {
        "id": "foo",
        "duration_ms": 5,
        "explicit": True,
        "uri": "bar",
        "name": "Track Name",
        "href": "https://foo",
        "track_number": 4,
    }
    got = fix.Track.from_result(data)
    assert isinstance(got, fix.Track)


@pytest.mark.parametrize(
    "fake_data, want",
    [
        ("spotify_id,album\nfoo,bar" "", {"foo"}),
        ("name,spotify_id,album\napple,foo,bar" "", {"foo"}),
        ("spotify_id\nfoo\nbar", {"foo", "bar"}),
        # Different line ending
        ("spotify_id\r\nfoo", {"foo"}),
    ],
)
def test_read_skiplist_file(fake_data: str, want: str, tmp_path: Path):
    # Create the fake skiplist file.
    path = tmp_path / "skiplist.csv"
    path.write_text(fake_data)

    got = fix.read_skiplist_file(path)
    assert got == want
