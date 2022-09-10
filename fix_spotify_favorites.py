from __future__ import annotations

import sys
import urllib.parse
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Tuple

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

    def __str__(self):
        return f"Track('{self.name}')"

    def __repr__(self):
        return str(self)

    @classmethod
    def from_result(cls, data: Dict) -> Track:
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
    artist_name: str
    tracks: List[Track]

    def __str__(self):
        return f"Album({self.artist_name}: '{self.name}')"

    def __repr__(self):
        return str(self)

    @classmethod
    def from_result(cls, data: Dict) -> Album:
        tracks = [Track.from_result(t) for t in data["tracks"]["items"]]

        return cls(
            spotify_id=data["id"],
            uri=data["uri"],
            name=data["name"],
            album_type=data["album_type"],
            href=data["href"],
            release_date=data["release_date"],
            release_date_precision=data["release_date_precision"],
            artist_name=",".join(art["name"] for art in data["artists"]),
            tracks=tracks,
        )


@dataclass
class Artist:
    pass


def get_all_saved_albums(sp: spotipy.Spotipy) -> List[Album]:
    offset = 0
    limit = 10

    logger.debug("Getting all saved albums.")
    logger.trace(f"Getting first {limit} albums.")
    results = sp.current_user_saved_albums(limit=limit, offset=offset)
    expected_total = results["total"]
    _albums = results["items"]

    while results["next"]:

        # Most of this is just for logging. /shrug
        # if results["next"]:
        _query = urllib.parse.urlparse(results["next"]).query
        new_offset = int(urllib.parse.parse_qs(_query)["offset"][0])

        logger.trace(
            f"Getting next {limit} albums"
            f" (offset: {new_offset}, total: {expected_total})"
        )
        results = sp.next(results)
        _albums.extend(results["items"])

    albums = [Album.from_result(album["album"]) for album in _albums]

    actual_total = len(albums)
    if expected_total != len(albums):
        raise ValueError(
            f"Retrived total {actual_total} does not match expected {expected_total}"
        )
    logger.debug(f"Found {actual_total} saved albums")
    return albums


def main(dry_run: bool = True) -> None:
    # Create our client
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    added_tracks: List[Tuple[Track, Album]] = []

    albums = get_all_saved_albums(sp)

    for album in albums:
        logger.debug(f"Processing {album}")

        for track in album.tracks:
            logger.trace(f"Processing {track}")

            # only checking 1 track at a time.
            if not sp.current_user_saved_tracks_contains([track.uri])[0]:
                if track.uri not in track_blocklist:

                    logger.info(f"Adding {track} from {album} to saved tracks.")
                    added_tracks.append((track, album))
                    if not dry_run:
                        sp.current_user_saved_tracks_add(track)

    num_added = len(added_tracks)
    logger.info(f"Added {num_added} tracks to saved tracks. Yay! 🎉")
    if dry_run:
        logger.warning("Dry Run: no tracks added.")


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
