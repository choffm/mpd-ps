# mpd-ps
MPD Playlist Synchronizer: A small python tool with numerous features, which copies the audio files from the current MPD playlist to a target directory. 

Dependencies:
=============
- Python 3
- python-mpd2 (https://github.com/Mic92/python-mpd2)
- Optional for any transcoding: python-mutagen
- Optional for transcoding FLAC/MP3/M4A to OGG/OPUS/MP3: ffmpeg with libvorbis / libopus / libmp3lame support

Features:
============
- Incrementally syncs the current MPC playlist with a target directory / device
- Optionally deletes files removed from MPD playlist
- Optionally syncs album art
- Optionally multi-threaded transcoding from FLAC, MP4 (.m4a) and MP3 to ogg vorbis, opus or lame mp3 using ffmpeg
- Optionally bitrate dependend lossy to lossy transcoding, configurable separately for MP3 and M4A
- Configuration via config file (Default: ./mpd-ps.conf, $HOME/.config/mpd-ps/mpd-ps.conf or $HOME/AppData/Roaming/mpd-ps/mpd-ps.conf)

Usage:
============
mpd-ps is controlled by mpd-ps.conf. An example file is included and must be placed either in $HOME/.config/mpd-ps/mpd-ps.conf respectively $USERHOME\APPDATA\Roaming\mpd-ps\mpd-ps.conf. Placing the config file in the same folder as the python script deactivates the config file in the config / APPDATA folder.

At least the source (src) and destination (dst) folder must be specified, all other options are optional. By default, FLAC files are transcoded to opus at 96kbit/s, lossy files are copied. See the packaged config file for other default values. 

The threshold values define the lowest bitrate in bit/sec at which mp3/m4a files are not transcoded (if lossy transcoding is exlpicitely enabled).

