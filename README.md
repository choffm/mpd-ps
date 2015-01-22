# mpd-ps
MPD Playlist Synchronizer: A small python tool with numerous features, which copies the audio files in the current MPD playlist to a target directory. 

Dependencies:
=============
- Python 3
- python-mpd2 (https://github.com/Mic92/python-mpd2)
- Optional for transcoding FLAC to OGG/MP3: oggenc / lame
- Optionally for transcoding to MP3: python-mutagen

Features:
============
- Incrementally syncs the current MPC playlist with a target directory / device
- Optionally deletes files removed from MPD playlist
- Optionally syncs album art
- Optionally transcodes .flac files to ogg vorbis or mp3 using oggenc and lame encoder
- Multi-threaded transcoding of flac to MP3 or OGG Vorbis 

Usage:
============

usage: mpd-ps.py [-h] [--encoder ENCODER] [--copy-flac] [--threads THREADS]
                 [--host HOST] [--port PORT] [--password PASSWORD]
                 [--delete-non-existent] [--dont-copy-album-art]
                 mpd-music-folder destination-folder

positional arguments:
  mpd-music-folder      root folder of mpd server
  destination-folder    folder where the audio files are copied / transcoded
                        to

optional arguments:
  -h, --help            show this help message and exit
  --encoder ENCODER     "ogg" for ogg vorbis q4 (~130kb/s) or "mp3" for lame
                        V2 (~180kb/s). Default: ogg q4, 44,1khz
  --copy-flac           copy flac files instead of transcoding them
  --threads THREADS     Amount of parallel encoding processes when transcoding
                        flac files. Default: Auto-detect
  --host HOST           adress of mpd server. Default: localhost
  --port PORT           port of mpd server. Default: 6600
  --password PASSWORD   password of mpd server.
  --delete-non-existent
                        delete files from destination which are not in mpd
                        playlist. Also deletes empty directories in
                        destination folder
  --dont-copy-album-art
                        do not copy .jpg and .png album art to destination.
