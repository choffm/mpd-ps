# mpd-ps
MPD Playlist Synchronizer: A small python tool with numerous features, which copies the audio files in the current MPD playlist to a target directory. 

Dependencies:
=============
- Python 3
- python-mpd2 (https://github.com/Mic92/python-mpd2)
- Optional for transcoding FLAC to OGG/MP3: GNU parallel, oggenc or lame

Features:
============
- Incrementally syncs the current MPC playlist with a target directory / device
- Optionally deletes files removed from MPD playlist
- Optionally syncs album art
- Optionally transcodes .flac files to ogg vorbis or mp3 using oggenc and lame encoder
- Multi-threaded transcoding: Using gnu parallel, flac files are transcoded simultaneously 
