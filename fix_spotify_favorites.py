from __future__ import annotations

import csv
import datetime as dt
import itertools
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

import click
import loguru
import spotipy
from loguru import logger
from spotipy.oauth2 import SpotifyOAuth

SKIPLIST_PATH = Path(__file__).parent / "skiplist.csv"
LOG_FILE = Path(__file__).parent / "fix-spotify-favorites.log"


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--dry-run", is_flag=True, help="Do not update 'Liked' songs.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase printed messages. Can be provided multiple times.",
)
@click.option(
    "-s",
    "--skiplist-file",
    type=click.Path(exists=False, dir_okay=False),
    default=SKIPLIST_PATH,
    help="The file containing skiplisted track IDs. See README for required format.",
)
def cli(verbose: int, dry_run: bool, skiplist_file: Path):
    setup_logging(logger, verbose)
    main(dry_run=dry_run, skiplist_file=skiplist_file)


def setup_logging(logger: loguru.Logger, verbose: int):
    levels = {
        0: "SUCCESS",
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
    logger.add(LOG_FILE, level="TRACE")
    logger.info(f"Console verbosity set to {verbose} ({levels[verbose]}).")


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
class AddedTrack:
    track: Track
    album: Album


def read_skiplist_file(path: Path) -> Set[str]:
    skipped_ids: List[str] = []
    with path.open("r", newline="") as openf:
        reader = csv.DictReader(openf)
        for row in reader:
            skipped_ids.append(row["spotify_id"])
    return set(skipped_ids)


def get_all_saved_albums(sp: spotipy.Spotipy) -> List[Album]:
    offset = 0
    limit = 50

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
    logger.success(f"Found {actual_total} saved albums")
    return albums


def main(
    dry_run: bool = True, skiplist_file: Optional[Path] = None
) -> List[AddedTrack]:
    logger.success(f"Starting. {dry_run=}, {skiplist_file=}")
    start_time = dt.datetime.utcnow()

    skiplist: Set[str] = set()
    if skiplist_file is None or not skiplist_file.exists():
        logger.info(f"Skiplist file {skiplist_file} does not exist or was not given.")
    else:
        skiplist = read_skiplist_file(skiplist_file)

    # Create our client
    scope = "user-library-read"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    added_tracks: List[AddedTrack] = []

    albums = get_all_saved_albums(sp)

    for n, album in enumerate(albums):
        logger.debug(f"Processing album {n} of {len(albums)}: {album}")
        tracks = album.tracks

        track_uris: List[str] = [track.uri for track in tracks]
        already_liked: List[bool] = sp.current_user_saved_tracks_contains(track_uris)

        # [a, b, c] + [True, True, False] => [c]
        need_to_add: List[Track] = list(
            itertools.compress(tracks, (not liked for liked in already_liked))
        )

        if not need_to_add:
            logger.trace(f"All tracks from {album} are already 'liked'.")
            continue

        # Remove any skiplisted tracks.
        # Note that we iterate over a *copy* of the list so that we can modify it.
        original_need_to_add = need_to_add[:]
        for track in need_to_add[:]:
            if track.spotify_id in skiplist:
                need_to_add.remove(track)
                logger.warning(
                    f"Skipping {track} from {album} because it's in the skiplist file."
                )

        if not need_to_add:
            logger.info(
                f"All {len(original_need_to_add)} potential tracks from {album}"
                " that could be added to the 'Saved Tracks' list are present"
                " in the skiplist file. Nothing to do."
            )
            continue

        logger.info(
            f"Adding {len(need_to_add)} tracks from {album} to saved"
            f" tracks: {need_to_add}"
        )
        added_tracks.extend([AddedTrack(track, album) for track in need_to_add])

        if not dry_run:
            sp.curren_user_saved_tracks_add([t.uri for t in need_to_add])

    end_time = dt.datetime.utcnow()
    duration = end_time - start_time
    num_added = len(added_tracks)
    logger.success(f"Added {num_added} tracks to saved tracks. Yay! 🎉")
    logger.info(f"Took {duration} to run.")
    if dry_run:
        logger.warning("Dry Run: no tracks added.")

    return added_tracks


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
