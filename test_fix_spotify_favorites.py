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
