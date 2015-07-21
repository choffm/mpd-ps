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
import configparser
from mutagen.flac import FLAC

def remove_empty_dirs(path):
    for root, dirnames, filenames in os.walk(path, topdown=False):
        for dirname in dirnames:
            for dirpath, dirnames2, filenames2 in os.walk(os.path.join(root, dirname)):
                if not filenames2 and not dirnames2:
                    logger.debug(os.path.join(root, dirpath) + " is empty. Deleting empty directory.")
                    os.rmdir(os.path.join(root, dirpath))

platform = platform.system().lower()
parser = argparse.ArgumentParser()
parser.add_argument("--config", help="specify path to config file.",
                    dest="config")
parser.add_argument("--audio-format", help="\"ogg\" for ogg vorbis q4 (~130kb/s), \"opus\" for opus (~96kbit/s) or \"mp3\" for lame V2 (~180kb/s)."
                                      " Default: opus",
                    dest="audio_format")
parser.add_argument("--copy-flac", help="copy flac files instead of transcoding them",
                    action="store_true")
parser.add_argument("--verbose", help="Print more information",
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

parser.add_argument("mpd_music_folder", nargs='?', metavar="mpd-music-folder", help="root folder of mpd server")
parser.add_argument("destination_folder", nargs='?', metavar="destination-folder", help="folder where the audio files are copied / transcoded to")

args = parser.parse_args()

if args.config:
    config_file = args.config
else:
    if platform == "windows":
        config_file = os.path.join(os.getenv("APPDATA"), "mpd-ps", "mpd-ps.conf")
    else:
        config_file = os.path.join(os.path.expanduser("~"), ".config", "mpd-ps", "mpd-ps.conf")

host = "localhost"
port = ""
password = ""
mpd_root_dir = ""
dest_dir = ""
audio_format = "opus"
copy_flac = False
threads = ""
verbose = False

##Parse config file
config = configparser.RawConfigParser()
config.read(config_file)
if os.path.exists(config_file):
    if config.has_section('Host'):
        if config.has_option('Host', 'host'):
            host = config.get('Host', 'host')
        if config.has_option('Host', 'port'):
            port = config.get('Host', 'port')
        if config.has_option('Host', 'password'):
            password = config.get('Host', 'password')
    if config.has_section('General'):
        if config.has_option('General', 'mpd_music_folder'):
            mpd_root_dir = config.get('General', 'mpd_music_folder')
        if config.has_option('General', 'dest_dir'):
            dest_dir = config.get('General', 'dest_dir')
        if config.has_option('General', 'audio_format'):
            audio_format = config.get('General', 'audio_format')
        if config.has_option('General', 'copy_flac'):
            copy_flac = config.getboolean('General', 'copy_flac')
        if config.has_option('General', 'threads'):
            threads = config.getint('General', 'threads')
        if config.has_option('General', 'verbose'):
            verbose = config.getboolean('General', 'verbose')

##Parse command line arguments
logger = logging.getLogger("mpd-ps")
if args.verbose or verbose:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

if (os.path.exists(config_file)):
    logger.info('Using configuration file: ' + config_file)

if args.mpd_music_folder:
    mpd_root_dir = args.mpd_music_folder
elif not mpd_root_dir:
    logger.error("Please specify the root folder of mpd server with -in parameter.")
    exit()

if args.destination_folder:
    dest_dir = args.destination_folder
elif not dest_dir:
    logger.error("Please specify the output folder with -out parameter.")
    exit()

if args.audio_format:
    audio_format = args.audio_format
elif audio_format == "":
    audio_format = "opus"
if audio_format != "ogg" and audio_format != "mp3" and audio_format != "opus":
        logger.error("Bad audio format parameter.")
        exit(-1)

if args.copy_flac or copy_flac:
    copy_flac = True
    if audio_format:
        logger.warn("Copying flac files instead of transcoding. Specified audio format settings is ignored.")
elif not copy_flac:
    copy_flac = False

if args.host:
    host = args.host
elif not host:
    host = "localhost"

if args.port:
    port = args.port
elif not port:
    port = 6600

if args.password:
    password = args.password
elif not password:
    password = ""

if args.threads and args.threads > 0:
    threads = args.threads
elif not threads or threads <= 0:
    threads = multiprocessing.cpu_count()

logger.info('Host: ' + host + ":" + str(port))
logger.info('MPD music folder: ' + mpd_root_dir)
logger.info('Destination folder: ' + dest_dir)
logger.info('FLAC files:' + 'copy' if copy_flac else 'transcode to ' + audio_format)
logger.info('Transcoder threads: ' + str(threads))

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
flac_files_size = 0
size = 0
mytime = 0
added_files = set()
folders = {}
count = 0

item_size = 0

##Start the sync
for item in playlist:
    if item_size % 10 == 0:
        logger.info("Processed " + str(item_size) + "/" + str(len(playlist)) + " files ("+str(int(100*item_size/len(playlist)))+"%).")
    src_full_path = os.path.join(mpd_root_dir,item[6:]) #exclude "file: "
    src_path = src_full_path[:src_full_path.rfind('/')+1] #stripped filename
    item_short_path = item[:item.rfind('/')+1] #relative path without filename

    dest_full_path = os.path.join(dest_dir,item[6:]) #exclude "file " (: replaced by re.sub()
    dest_path = dest_full_path[:dest_full_path.rfind('/')+1]
    filename = dest_full_path[dest_full_path.rfind('/')+1:]

    folders[src_path] = dest_path
    item_size += 1
    # Skip existing files
    if os.path.isfile(dest_full_path) and os.path.getsize(dest_full_path) == os.path.getsize(src_full_path):
        logger.debug("file " + dest_full_path + " exists. Skipping.")
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
                flac_files_size += 1

            else:
                flac_files[item_short_path[6:]] = []
                flac_files[item_short_path[6:]].append(item[6:])
                flac_files_size += 1
        else:
            logger.debug("Transcoded file exists: " + transcoded_file)

    # Copy non-flac media files directly to destination
    else:
        added_files.add(dest_full_path)
        cur_time = current_milli_time()
        try:
            shutil.copy(src_full_path,dest_full_path)
            count+=1
            logger.debug("Copied file to: " + dest_full_path)

            mytime += (current_milli_time() - cur_time) / 1000
            size += os.path.getsize(dest_full_path) / (1024*1024)
            if mytime != 0:
                logger.debug("Transferred " + str(count) + " files with " + str(size / mytime)[:str(size / mytime).find(".")+3] + "MB/s")
        except OSError:
            logger.error("Copying " + src_full_path + " to " + dest_full_path + " failed. Skipping file.")

logger.info("Transferred " + str(size)[:str(size).find(".")+3] + " MB.")

if flac_files:
    logger.info("Start transcoding flac files now.")
    done = 0
    processes = set()
    for list in flac_files:
        if audio_format == "ogg":
            for file in flac_files[list]:
                logger.debug("Encoding " + os.path.join(dest_dir,file[:-4] + "ogg"))
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
        elif audio_format == "mp3":
            for file in flac_files[list]:
                audio = FLAC(os.path.join(mpd_root_dir,file))
                title = "" if audio.get("title") == None else audio.get("title")[0]
                artist = "" if audio.get("artist") == None else audio.get("artist")[0]
                album = "" if audio.get("album") == None else audio.get("album")[0]
                genre = "" if audio.get("genre") == None else audio.get("genre")[0]
                tracknumber = "" if audio.get("tracknumber") == None else audio.get("tracknumber")[0]
                date = "" if audio.get("date") == None else audio.get("date")[0]

                logger.debug("Encoding " + os.path.join(dest_dir,file[:-4] + "mp3"))
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
        elif audio_format == "opus":
            for file in flac_files[list]:
                logger.debug("Encoding " + os.path.join(dest_dir,file[:-4] + "opus"))
                processes.add(subprocess.Popen(["ffmpeg", "-i", os.path.join(mpd_root_dir,file),
                                                "-c", "libopus", os.path.join(dest_dir,file[:-4] + "opus")],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                if platform == "windows":
                    while len(processes) >= threads:
                        time.sleep(.1) #for windows compatibility
                        processes.difference_update([p for p in processes if p.poll() is not None])
                else:
                    if len(processes) >= threads:
                        os.wait()
                        processes.difference_update([p for p in processes if p.poll() is not None])
        done += len(flac_files[list])
        logger.info("Encoded " + str(done) + "/" + str(flac_files_size) + " files ("+str(int(100*done/flac_files_size))+"%).")
logger.info("Start Copying album art now.")
# Copying image files (jpg,png) to destination (covers etc)

if not args.dont_copy_album_art:
    for src in folders:
        for file in os.listdir(src):
            if file.endswith(".jpg") or file.endswith(".png"):
                added_files.add(folders[src] + file)
                if not os.path.isfile(os.path.join(folders[src],file)):
                    shutil.copy(src+file,os.path.join(folders[src],file))
                    logger.debug("Copies image: " + file + " to " + folders[src])
                else:
                    logger.debug("Cover exists: " + folders[src] + file)

if args.delete_non_existent:
    logger.info("Start removing files now.")
    # Remove files from destination that are not in playlist any more
    dest_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(dest_dir) for f in filenames]
    for f in dest_files:
        if not f in added_files:
            logger.debug("File " + f + " is not in playlist any more. Removing it.")
            os.remove(f)
    # Remove potential empty directories after deleting stuff.
    remove_empty_dirs(dest_dir)

logger.info("Finished playlist synchronization.")