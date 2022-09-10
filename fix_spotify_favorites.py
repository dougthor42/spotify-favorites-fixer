from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional

import click
import loguru
import spotipy
from loguru import logger
from spotipy.oauth2 import SpotifyOAuth

track_blocklist: List[str] = []


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--dry-run", is_flag=True, help="Do not update 'Liked' songs.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase printed messages. Can be provided multiple times.",
)
def cli(verbose: int, dry_run: bool):
    setup_logging(logger, verbose)
    main(dry_run=dry_run)


def setup_logging(logger: loguru.Logger, verbose: int):
    levels = {
        0: "WARNING",
        1: "INFO",
        2: "DEBUG",
        3: "TRACE",
    }
    if verbose > 3:
        verbose = 3
    if verbose < 0:
        verbose = 0

    logger.remove()
    logger.add(sys.stderr, level=levels[verbose])
    logger.info(f"Verbosity set to {verbose} ({levels[verbose]}).")


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


def main(dry_run: bool = False) -> None:
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
    cli()
