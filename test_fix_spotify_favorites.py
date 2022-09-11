from pathlib import Path
from typing import Optional
from typing import Set

import pytest

import fix_spotify_favorites as fix

_fake_track = {
    "id": "foo",
    "duration_ms": 5,
    "explicit": True,
    "uri": "bar",
    "name": "Track Name",
    "href": "https://foo",
    "track_number": 4,
}


def test_Track_from_result():
    got = fix.Track.from_result(_fake_track)
    assert isinstance(got, fix.Track)
    assert got._data == _fake_track
    assert got.uri == "bar"


def test_Album_from_result():
    data = {
        "id": "foo",
        "uri": "bar",
        "name": "An Album Cover",
        "album_type": "album",
        "href": "https://foo",
        "release_date": "2022-04-01",
        "release_date_precision": "day",
        "artists": [{"name": "Weird Al"}, {"name": "Tenacious D"}],
        "tracks": {"items": [_fake_track, _fake_track]},
    }
    got = fix.Album.from_result(data)
    assert isinstance(got, fix.Album)
    assert got._data == data
    assert len(got.tracks) == 2
    assert got.artist_name == "Weird Al,Tenacious D"


@pytest.mark.parametrize(
    "path, want",
    [
        (None, set()),
        (Path("foo.csv"), set()),
        (Path(__file__), {"foo", "bar"}),
    ],
)
def test_read_skiplist_file(path: Optional[Path], want: Set[str], monkeypatch):
    monkeypatch.setattr(fix, "parse_skiplist_file", lambda _: want)
    got = fix.read_skiplist_file(path)
    assert got == want


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
def test_parse_skiplist_file(fake_data: str, want: str, tmp_path: Path):
    # Create the fake skiplist file.
    path = tmp_path / "skiplist.csv"
    path.write_text(fake_data)

    got = fix.parse_skiplist_file(path)
    assert got == want
