from __future__ import annotations

import csv
import datetime as dt
import itertools
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
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
LOG_FILE = Path(__file__).parent / "log" / "fix-spotify-favorites_{time}.log"

TSV_HEADERS = ["artist", "album", "track", "track_num"]


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
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    default=SKIPLIST_PATH,
    help="The file containing skiplisted track IDs. See README for required format.",
)
@click.option(
    "--save-tsv",
    is_flag=True,
    default=False,
    help="Save a tsv file of all 'Liked' tracks to ./tracks.tsv",
)
def cli(verbose: int, dry_run: bool, skiplist_file: Path, save_tsv: bool) -> None:
    setup_logging(logger, verbose)
    main(dry_run=dry_run, skiplist_file=skiplist_file, save_tsv=save_tsv)


def setup_logging(logger: loguru.Logger, verbose: int) -> None:
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
    _data: Dict[str, Any]

    def __str__(self) -> str:
        return f"Track('{self.spotify_id}: {self.name}')"

    def __repr__(self) -> str:
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
            _data=data,
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
    _data: Dict[str, Any]

    def __str__(self) -> str:
        return f"Album({self.artist_name}: '{self.name}')"

    def __repr__(self) -> str:
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
            _data=data,
        )


@dataclass
class AddedTrack:
    track: Track
    album: Album


def parse_skiplist_file(path: Path) -> Set[str]:
    skipped_ids: List[str] = []
    with path.open("r", newline="") as openf:
        reader = csv.DictReader(openf)
        for row in reader:
            skipped_ids.append(row["spotify_id"])
    return set(skipped_ids)


def read_skiplist_file(path: Optional[Path]) -> Set[str]:
    """Read the skiplist file, if given and present."""
    skiplist: Set[str] = set()
    if path is None or not path.exists():
        logger.warning(f"Skiplist file '{path}' does not exist or was not given.")
    else:
        skiplist = parse_skiplist_file(path)

    return skiplist


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


def filter_tracks_to_add(sp: spotipy.Spotify, tracks: List[Track]) -> List[Track]:
    """Remove any tracks that the user has already 'liked'."""
    track_uris: List[str] = [track.uri for track in tracks]
    already_liked: List[bool] = sp.current_user_saved_tracks_contains(track_uris)

    # [a, b, c] + [True, True, False] => [c]
    need_to_add: List[Track] = list(
        itertools.compress(tracks, (not liked for liked in already_liked))
    )

    return need_to_add


def main(
    dry_run: bool = False,
    skiplist_file: Optional[Path] = None,
    save_tsv: bool = False,
) -> List[AddedTrack]:
    logger.success(f"Starting. {dry_run=}, {skiplist_file=}")
    start_time = dt.datetime.utcnow()

    skiplist = read_skiplist_file(skiplist_file)

    # Create our client
    scope = ["user-library-read"]
    if not dry_run:
        scope.append("user-library-modify")
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    added_tracks: List[AddedTrack] = []

    tsv_file = Path(__file__).parent / "tracks.tsv"
    if save_tsv:
        # Clear it out and make headers
        # Not using DictWriter for headers because this is simpler
        tsv_file.write_text("\t".join(TSV_HEADERS) + "\n")

    albums = get_all_saved_albums(sp)
    for n, album in enumerate(albums):
        logger.debug(f"Processing album {n} of {len(albums)}: {album}")
        tracks = album.tracks

        if save_tsv:
            with open(tsv_file, "a", newline="") as openf:
                tsv_writer = csv.DictWriter(
                    openf,
                    fieldnames=TSV_HEADERS,
                    delimiter="\t",
                    lineterminator="\n",
                )
                for track in tracks:
                    tsv_writer.writerow(
                        {
                            "artist": album.artist_name,
                            "album": album.name,
                            "track": track.name,
                            "track_num": track.track_number,
                        }
                    )

        need_to_add = filter_tracks_to_add(sp, tracks)
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

        logger.success(
            f"Adding {len(need_to_add)} tracks from {album} to saved"
            f" tracks: {need_to_add}"
        )
        added_tracks.extend([AddedTrack(track, album) for track in need_to_add])

        if not dry_run:
            sp.current_user_saved_tracks_add([t.uri for t in need_to_add])

    # Extra logging info
    end_time = dt.datetime.utcnow()
    duration = end_time - start_time
    num_added = len(added_tracks)
    if num_added:
        logger.success(f"Added {num_added} tracks to saved tracks. Yay! 🎉")
    else:
        logger.success("No tracks to add - everything's up to date! ✨")
    logger.info(f"Took {duration} to run.")

    if dry_run:
        logger.warning("Dry Run: no tracks added.")

    if save_tsv:
        logger.success(f"Saved all tracks to {tsv_file}")

    return added_tracks


if __name__ == "__main__":
    cli()
