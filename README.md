# Spotify Favorites Fixer

At some point in the past few years, Spotify changed how they handle the
"Liking" ("Favoriting") of songs and albums. Previously, if you "Liked" ❤️ an
album, all tracks in that album would also be "Liked" ❤️ and added to your
"Liked Songs" list.

Nowadays, that's no longer the case: "Liking" an album simply adds it to **Your
Library** --> **Albums** and does nothing to the "Liked Songs" list.

I really dislike (ha!) this change, so I've finally decided to do something about
it.

This simple script will query all of your "Liked" albums and then mark each
track as "Liked" as well.

Sure, it's got it's downsides - if you "Un-Like" a track from a "Liked" album,
this script will "Re-Like" it for you. But that's something we just deal with.

Also, [Semantic Satiation][semantic-satiation] of "Like"...


## Settings Things Up

1.  Make sure you have a [Spotify Developer][spotify-developer] account.
2.  Create an App. Any name is fine.
3.  Add `http://127.0.0.1:9090` as a Redirect URI on the App.
3.  Add your client ID and client secret into `.\secrets.sh`:
    ```shell
    export SPOTIPY_CLIENT_ID="<client_id>"
    export SPOTIPY_CLIENT_SECRET="<client_secret>"
    export SPOTIPY_REDIRECT_URI="http://127.0.0.1:9090"
    ```
4.  Source that file: `source secrets.sh`


## Installation

1.  Clone the repo.
2.  Make a venv and activate it.
3.  Install: `pip install -e .`


### Development

Do the 3 steps above, and then:

1.  Install dev dependencies: `pip install -e .[develop]`
2.  Install pre-commit hooks: `pre-commit install`
3.  Run tests if you want: `pytest`


## Usage

If you've done [Settings Things Up](#setting-things-up) and
[Installation](#installation) then you should be able to just call:

```
python fix_spotify_favorites.py
```

A browser window will pop up asking for authorization to access your data.
Give it the A-OK and the script will do its thing.

Authorization will last for... some amount of time. Maybe a day? I donno,
I haven't tested yet. During the active auth period, re-running the program
will _not_ pop up the browser window.

### CLI

View the CLI args/help with `python fix_spotify_favorites.py --help`.


### Skiplisting Tracks

Sometimes there are tracks that you intentionally "un-like". These can be
added to a file and then `fix_spotify_favorites` will not re-like it.

The skiplist file is a CSV file (named "skiplist.csv" by default). The file
**must** have the following properties:

+ column names on row 1
+ have a column called `spotify_id` which is the ID of the track to skip
+ use commas as a column delimiter (if multitple columns are present)

All other columns, along with ordering, are ignored so you can use them for
your own notes or whatever.

For example, these are all valid and equivalent skiplist files.
```csv
spotify_id,artist,track
6DZLcTwul48FE4aW0xSxbl,Sublime,Raleigh Soliloquy Pt. I
62oXSkYi2CJAz1hoJAvGN0,Sublime,Raleigh Soliloquy Pt. II
3ZBUmaRN1hitj5L0pJTifL,Wicked,No Good Deed (German)
```

```csv
reason,spotify_id,track
"Foo",6DZLcTwul48FE4aW0xSxbl,"Trackname 1"
"Bar",62oXSkYi2CJAz1hoJAvGN0,"Raleigh Soliloquy Pt. II"
"It's in German, man.",3ZBUmaRN1hitj5L0pJTifL,No Good Deed
```

```csv
spotify_id
6DZLcTwul48FE4aW0xSxbl
62oXSkYi2CJAz1hoJAvGN0
3ZBUmaRN1hitj5L0pJTifL
```


## Other

This was built on Python 3.8 and should run on any higher versions.

It uses the [Spotipy][spotipy] library and uses the [Authorization Code
Flow][spotipy-acf].

Only tested on Linux (WSL) Ubuntu 20.04.


[semantic-satiation]: https://en.wikipedia.org/wiki/Semantic_satiation
[spotify-developer]: https://developer.spotify.com
[spotipy]: https://github.com/plamere/spotipy
[spotipy-acf]: https://spotipy.readthedocs.io/en/master/#authorization-code-flow
