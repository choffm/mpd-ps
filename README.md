# mpd-ps
MPD Playlist Synchronizer: A small python tool with numerous features, which copies the audio files from the current MPD playlist to a target directory. 

Dependencies:
=============
- Python 3
- python-mpd2 (https://github.com/Mic92/python-mpd2)
- Optional for transcoding FLAC to OGG/MP3: oggenc / lame
- Optional for transcoding FLAC to MP3: python-mutagen
- Optional for transcoding FLAC to OPUS: ffmpeg with libopus support

Features:
============
- Incrementally syncs the current MPC playlist with a target directory / device
- Optionally deletes files removed from MPD playlist
- Optionally syncs album art
- Optionally transcodes .flac files to ogg vorbis, opus or mp3 using oggenc, ffmpeg/libopus and lame mp3 encoder
- Multi-threaded transcoding of flac to MP3 or OGG Vorbis 
- Supports config file (Default: ~/.config/mpd-ps/mpd-ps.conf or HOME/AppData/Roaming/mpd-ps/mpd-ps.conf)

