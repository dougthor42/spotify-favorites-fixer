from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

track_blocklist: List[str] = []
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# Some helper classes to make accessors easier.
@dataclass
class Track:
    spotify_id: str
    duration_ms: int
    explicit: bool
    uri: str
    name: str
    href: str
    track_number: int
    album: Optional[Album] = None

    def __str__(self):
        return f"Track('{self.name}')"

    def __repr__(self):
        return str(self)

    @classmethod
    def from_result(cls, data: Dict) -> Track:
        album = data.get("album", None)
        if album:
            album = Album.from_result(data["album"])

        return cls(
            spotify_id=data["id"],
            duration_ms=data["duration_ms"],
            explicit=data["explicit"],
            uri=data["uri"],
            name=data["name"],
            href=data["href"],
            track_number=data["track_number"],
        )


@dataclass
class Album:

    spotify_id: str
    uri: str
    name: str
    album_type: str  # album, single, compilation
    href: str
    release_date: str
    release_date_precision: str
    tracks: Optional[List[Track]] = None

    def __str__(self):
        return f"Album('{self.name}')"

    def __repr__(self):
        return str(self)

    @classmethod
    def from_result(cls, data: Dict) -> Album:
        tracks = data.get("tracks", None)
        if tracks:
            tracks = [Track.from_result(t) for t in tracks["items"]]

        return cls(
            spotify_id=data["id"],
            uri=data["uri"],
            name=data["name"],
            album_type=data["album_type"],
            href=data["href"],
            release_date=data["release_date"],
            release_date_precision=data["release_date_precision"],
            tracks=tracks,
        )


@dataclass
class Artist:
    pass


def main():
    # Create our client
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    album_results = sp.current_user_saved_albums(limit=20, offset=0)

    while album_results["next"]:
        albums = album_results["items"]

        for _album in albums:
            album = Album.from_result(_album["album"])

            for track in album.tracks:

                # only checking 1 track at a time.
                if not sp.current_user_saved_tracks_contains([track.uri])[0]:
                    if track.uri not in track_blocklist:

                        logger.info(f"Adding {album}::{track} to saved tracks.")
                        #  sp.current_user_saved_tracks_add(track)


def _example():
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    results = sp.current_user_saved_tracks(limit=50)
    track_names = [t["track"]["name"] for t in results["items"]]
    while results["next"]:
        logger.info(results["next"])
        results = sp.next(results)
        track_names.extend([t["track"]["name"] for t in results["items"]])

    print(len(track_names))
    print(track_names[:10])
    return track_names


if __name__ == "__main__":
    _example()
