__author__ = 'Clemens Hoffmann [clemens [at] vibee.de'

from mpd import MPDClient
import os
import shutil
import time
import logging
import argparse
import subprocess
import platform
import multiprocessing
from mutagen.flac import FLAC


def remove_empty_dirs(path):
    for root, dirnames, filenames in os.walk(path, topdown=False):
        for dirname in dirnames:
            for dirpath, dirnames2, filenames2 in os.walk(os.path.join(root, dirname)):
                if not filenames2 and not dirnames2:
                    logger.info(os.path.join(root, dirpath) + " is empty. Deleting empty directory.")
                    os.rmdir(os.path.join(root, dirpath))

parser = argparse.ArgumentParser()

parser.add_argument("--audio-format", help="\"ogg\" for ogg vorbis q4 (~130kb/s) or \"mp3\" for lame V2 (~180kb/s)."
                                      " Default: ogg q4, 44,1khz",
                    dest="audio_format")
parser.add_argument("--copy-flac", help="copy flac files instead of transcoding them",
                    action="store_true")
parser.add_argument("--threads", help="Amount of parallel encoding processes when transcoding flac files. Default: Auto-detect", type=int,
                    dest="threads")
parser.add_argument("--host", help="adress of mpd server. Default: localhost",
                    dest="host")
parser.add_argument("--port", help="port of mpd server. Default: 6600", type=int,
                    dest="port")
parser.add_argument("--password", help="password of mpd server.",
                    dest="password")
parser.add_argument("--delete-non-existent", help="delete files from destination which are not in mpd playlist. Also deletes empty "
                                                  "directories in destination folder", action="store_true")
parser.add_argument("--dont-copy-album-art", help="do not copy .jpg and .png album art to destination.",
                    action="store_true")

parser.add_argument("mpd_music_folder", metavar="mpd-music-folder", nargs=1, help="root folder of mpd server")
parser.add_argument("destination_folder", metavar="destination-folder", nargs=1, help="folder where the audio files are copied / transcoded to")

args = parser.parse_args()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mpd-ps")

if args.mpd_music_folder:
    mpd_root_dir = args.mpd_music_folder[0]
else:
    logger.error("Please specify the root folder of mpd server with -in parameter.")
    exit()

if args.destination_folder:
    dest_dir = args.destination_folder[0]
else:
    logger.error("Please specify the output folder with -out parameter.")
    exit()

if args.audio_format:
    audio_format = args.audio_format
    if audio_format != "ogg" and audio_format != "mp3":
        logger.error("Bad audio format parameter.")
        exit(-1)
else:
    audio_format = "ogg"

if args.copy_flac:
    copy_flac = True
    if args.audio_format:
        logger.warn("Copying flac files instead of transcoding. Specified audio format settings is ignored.")
else:
    copy_flac = False

if args.host:
    host = args.host
else:
    host = "localhost"

if args.port:
    port = args.port
else:
    port = 6600

if args.password:
    password = args.password
else:
    password = ""

if args.threads and args.threads > 0:
    threads = args.threads
else:
    threads = multiprocessing.cpu_count()

current_milli_time = lambda: int(round(time.time() * 1000))

client = MPDClient()
client.timeout = 10
client.idletimeout = None          # timeout for fetching the result of the idle command is handled seperately, default: None

client.connect(host, port)  # connect to localhost:6600
client.password(password)

playlist = client.playlist()          # print the MPD version
client.close()                     # send the close command
client.disconnect()                # disconnect from the server

flac_files = {}
size = 0
mytime = 0
added_files = set()
folders = {}
count = 0
platform = platform.system().lower()


for item in playlist:

    src_full_path = os.path.join(mpd_root_dir,item[6:]) #exclude "file: "
    src_path = src_full_path[:src_full_path.rfind('/')+1] #stripped filename
    item_short_path = item[:item.rfind('/')+1] #relative path without filename

    dest_full_path = os.path.join(dest_dir,item[6:]) #exclude "file " (: replaced by re.sub()
    dest_path = dest_full_path[:dest_full_path.rfind('/')+1]
    filename = dest_full_path[dest_full_path.rfind('/')+1:]

    folders[src_path] = dest_path

    # Skip existing files
    if os.path.isfile(dest_full_path) and os.path.getsize(dest_full_path) == os.path.getsize(src_full_path):
        logger.info("file " + dest_full_path + " exists. Skipping.")
        added_files.add(dest_full_path)
        continue

    # Create directories on destination, if they don't exist
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)

    # Transcode flac files to ogg vorbis q4 on destination
    if filename[filename.rfind('.')+1:] == "flac" and not copy_flac:
        os.environ ['infile'] = src_full_path
        transcoded_file = dest_full_path[:dest_full_path.rfind('.')] + "." + audio_format
        added_files.add(transcoded_file)
        os.environ['outfile'] = transcoded_file
        if not os.path.exists(transcoded_file):
            if item_short_path[6:] in flac_files:

                flac_files[item_short_path[6:]].append(item[6:])

            else:
                flac_files[item_short_path[6:]] = []
                flac_files[item_short_path[6:]].append(item[6:])

        else:
            logger.info("Transcoded file exists: " + transcoded_file)

    # Copy non-flac media files directly to destination
    else:
        added_files.add(dest_full_path)
        cur_time = current_milli_time()
        try:
            shutil.copy(src_full_path,dest_full_path)
            count+=1
            logger.info("Copied file to: " + dest_full_path)

            mytime += (current_milli_time() - cur_time) / 1000
            size += os.path.getsize(dest_full_path) / (1024*1024)
            if mytime != 0:
                logger.info("Transferred " + str(count) + " files with " + str(size / mytime)[:str(size / mytime).find(".")+3] + "MB/s")
        except OSError:
            logger.error("Copying " + src_full_path + " to " + dest_full_path + " failed. Skipping file.")

logger.info("Transferred " + str(size)[:str(size).find(".")+3] + " MB.")

if flac_files:
    logger.info("Start transcoding flac files now.")
    processes = set()
    for list in flac_files:
        if audio_format == "ogg":
            for file in flac_files[list]:
                logger.info("Encoding " + os.path.join(dest_dir,file[:-4] + "ogg"))
                processes.add(subprocess.Popen(["oggenc", "-q", "4", "--resample", "44100",
                                                os.path.join(mpd_root_dir,file), "-o", os.path.join(dest_dir,file[:-4] + "ogg")],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                if platform == "windows":
                    while len(processes) >= threads:
                        time.sleep(.1) #for windows compatibility
                        processes.difference_update([p for p in processes if p.poll() is not None])
                else:
                    if len(processes) >= threads:
                        os.wait()
                        processes.difference_update([p for p in processes if p.poll() is not None])
        else:
            for file in flac_files[list]:
                audio = FLAC(os.path.join(mpd_root_dir,file))
                title = "" if audio.get("title") == None else audio.get("title")[0]
                artist = "" if audio.get("artist") == None else audio.get("artist")[0]
                album = "" if audio.get("album") == None else audio.get("album")[0]
                genre = "" if audio.get("genre") == None else audio.get("genre")[0]
                tracknumber = "" if audio.get("tracknumber") == None else audio.get("tracknumber")[0]
                date = "" if audio.get("date") == None else audio.get("date")[0]

                logger.info("Encoding " + os.path.join(dest_dir,file[:-4] + "mp3"))
                ps = subprocess.Popen(["flac",  "-d", "-c", os.path.join(mpd_root_dir,file)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                ps2 = subprocess.Popen(["lame", "-V2", "--resample", "44.1", "--tt", title,
                                           "--ta", artist, "--tl", album, "--ty", date,
                                           "--tn", tracknumber, "--tg", genre, "--id3v2-only", "--id3v2-utf16"
                                           , "-", os.path.join(dest_dir,file[:-4] + "mp3")],
                                       stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                processes.add(ps2)
                if platform == "windows":
                    while len(processes) >= threads:
                        time.sleep(.1) #for windows compatibility
                        processes.difference_update([p for p in processes if p.poll() is not None])
                else:
                    while len(processes) >= threads:
                        os.wait()
                        processes.difference_update([p for p in processes if p.poll() is not None])

print("Start Copying album art now.")
# Copying image files (jpg,png) to destination (covers etc)

if not args.dont_copy_album_art:
    for src in folders:
        for file in os.listdir(src):
            if file.endswith(".jpg") or file.endswith(".png"):
                added_files.add(folders[src] + file)
                if not os.path.isfile(os.path.join(folders[src],file)):
                    shutil.copy(src+file,os.path.join(folders[src],file))
                    logger.info("Copies image: " + file + " to " + folders[src])
                else:
                    logger.info("Cover exists: " + folders[src] + file)

if args.delete_non_existent:
    print("Start removing files now.")
    # Remove files from destination that are not in playlist any more
    dest_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(dest_dir) for f in filenames]
    for f in dest_files:
        if not f in added_files:
            logger.info("File " + f + " is not in playlist any more. Removing it.")
            os.remove(f)
    # Remove potential empty directories after deleting stuff.
    remove_empty_dirs(dest_dir)


