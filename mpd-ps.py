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
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

import re

class transcode_job:
    def __init__(self,src,dest):
        self.src = src
        self.dest = dest

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
threads = ""
verbose = False
delete_non_existent = False
copy_album_art = True
transcode_flac = True
transcode_mp3 = False
transcode_m4a = False
transcode_m4a_threshold = 200000
transcode_mp3_threshold = 200000
audio_quality_lame = 3
audio_quality_opus = 96000
audio_quality_vorbis = 4

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
        if config.has_option('General', 'src'):
            mpd_root_dir = config.get('General', 'src')
        if config.has_option('General', 'dest'):
            dest_dir = config.get('General', 'dest')
        if config.has_option('General', 'audio_format'):
            audio_format = config.get('General', 'audio_format')
        if config.has_option('General', 'transcode_flac'):
            transcode_flac = config.getboolean('General', 'transcode_flac')
        if config.has_option('General', 'threads'):
            threads = config.getint('General', 'threads')
        if config.has_option('General', 'verbose'):
            verbose = config.getboolean('General', 'verbose')
        if config.has_option('General', 'delete_non_existent'):
            delete_non_existent = config.getboolean('General', 'delete_non_existent')
        if config.has_option('General', 'copy_album_art'):
            copy_album_art = config.getboolean('General', 'copy_album_art')
        if config.has_option('General', 'transcode_m4a'):
            transcode_m4a = config.getboolean('General', 'transcode_m4a')
        if config.has_option('General', 'transcode_m4a_threshold'):
            transcode_m4a_threshold = config.getint('General', 'transcode_m4a_threshold')
        if config.has_option('General', 'transcode_mp3'):
            transcode_mp3 = config.getboolean('General', 'transcode_mp3')
        if config.has_option('General', 'transcode_mp3_threshold'):
            transcode_mp3_threshold = config.getint('General', 'transcode_mp3_threshold')
        if config.has_option('General', 'audio_quality_lame'): # 0 - 10,
            audio_quality_lame = config.getint('General', 'audio_quality_lame')
        if config.has_option('General', 'audio_quality_vorbis'): # -1  - 10, fractions allowed
            audio_quality_vorbis = config.getfloat('General', 'audio_quality_vorbis')
        if config.has_option('General', 'audio_quality_opus'): # in bit/s
            audio_quality_opus = config.getint('General', 'audio_quality_opus')

##Parse command line arguments
logger = logging.getLogger("mpd-ps")
if verbose:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

if (os.path.exists(config_file)):
    logger.info('Using configuration file: ' + config_file)
else:
    logger.error('Configuration file ' + config_file + " doesn't not exist. Aborting.")
    exit(-1)

if not mpd_root_dir:
    logger.error("Please specify the root folder of mpd server within config file. (src=)")
    exit(-1)

if not dest_dir:
    logger.error("Please specify the destination folder within config file. (dest=)")
    exit(-1)

if audio_format == "":
    audio_format = "opus"
elif audio_format != "ogg" and audio_format != "mp3" and audio_format != "opus":
    logger.error("Bad audio format. mpd-ps supports ogg, opus and mp3.")
    exit(-1)

if not transcode_flac:
    logger.warn("Copying flac files instead of transcoding. Specified audio format settings is ignored.")

if not host:
    host = "localhost"

if not port:
    port = 6600

if not password:
    password = ""

if threads or threads <= 0:
    threads = multiprocessing.cpu_count()


logger.info('Host: ' + host + ":" + str(port))
logger.info('MPD music folder: ' + mpd_root_dir)
logger.info('Destination folder: ' + dest_dir)
logger.info('FLAC files:' + 'transcode to ' + audio_format if transcode_flac else 'copy')
logger.info('MP3 files:' + 'transcode to ' + audio_format + ' if bitrate > ' + str(transcode_mp3_threshold/1000) + 'kbit/s' if transcode_mp3 else 'copy')
logger.info('M4A files:' + 'transcode to ' + audio_format + ' if bitrate > ' + str(transcode_m4a_threshold/1000) + 'kbit/s' if transcode_m4a else 'copy')
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

transcode_jobs = {}
transcode_jobs_size = 0
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
    src_relative_name = item[6:]
    src_relativ_path = os.path.dirname(src_relative_name)
    src_absolute_name = os.path.join(mpd_root_dir,src_relative_name) #exclude "file: "
    src_absolute_path = os.path.dirname(src_absolute_name)

    dest_absolute_name = os.path.join(dest_dir,src_relative_name) #exclude "file " (: replaced by re.sub()
    dest_absolute_path = os.path.dirname(dest_absolute_name)

    transcode_file = False
    if src_absolute_name.endswith(".flac") and transcode_flac:
        transcode_file = True
        dest_absolute_name = re.sub(r".m4a$", "." + audio_format, dest_absolute_name)
        dest_absolute_name = re.sub(r".flac$", "." + audio_format, dest_absolute_name)

    if src_absolute_name.endswith(".mp3") and transcode_mp3:
        audio = MP3(src_absolute_name)
        if audio.info.bitrate >= transcode_mp3_threshold:
            transcode_file = True
            dest_absolute_name = re.sub(r".mp3$", "." + audio_format, dest_absolute_name)

    if src_absolute_name.endswith(".m4a") and transcode_m4a:
        audio = MP4(src_absolute_name)
        if audio.info.bitrate >= transcode_m4a_threshold:
            transcode_file = True
            dest_absolute_name = re.sub(r".m4a$", "." + audio_format, dest_absolute_name)

    folders[src_absolute_path] = dest_absolute_path
    item_size += 1
    # Skip existing files
    if os.path.isfile(dest_absolute_name) and os.path.getsize(dest_absolute_name) == os.path.getsize(src_absolute_name):
        logger.debug("file " + dest_absolute_name + " exists. Skipping.")
        added_files.add(dest_absolute_name)
        continue

    # Create directories on destination, if they don't exist
    elif not os.path.exists(dest_absolute_path):
        os.makedirs(dest_absolute_path)

    # Add file to transcode jobs dict if specified
    if transcode_file:
        added_files.add(dest_absolute_name)
        if not os.path.exists(dest_absolute_name):
            if src_relativ_path in transcode_jobs:
                transcode_jobs[src_relativ_path].append(transcode_job(src_absolute_name, dest_absolute_name))
                transcode_jobs_size += 1
            else:
                transcode_jobs[src_relativ_path] = []
                transcode_jobs[src_relativ_path].append(transcode_job(src_absolute_name, dest_absolute_name))
                transcode_jobs_size += 1
        else:
            logger.debug("Transcoded file exists: " + dest_absolute_name)

    # Copy all other audio files directly to destination
    else:
        added_files.add(dest_absolute_name)
        cur_time = current_milli_time()
        try:
            shutil.copy(src_absolute_name,dest_absolute_name)
            count+=1
            logger.debug("Copied file to: " + dest_absolute_name)

            mytime += (current_milli_time() - cur_time) / 1000
            size += os.path.getsize(dest_absolute_name) / (1024*1024)
            if mytime != 0:
                logger.debug("Transferred " + str(count) + " files with " + str(size / mytime)[:str(size / mytime).find(".")+3] + "MB/s")
        except OSError:
            logger.error("Copying " + src_absolute_name + " to " + dest_absolute_name + " failed. Skipping file.")

logger.info("Transferred " + str(size)[:str(size).find(".")+3] + " MB.")

if transcode_jobs:
    logger.info("Start transcoding audio files now.")
    done = 0
    processes = set()
    for list in transcode_jobs:
        for job in transcode_jobs[list]:
            logger.debug("Encoding file:" + job.dest)
            if audio_format == "ogg":
                processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                "-c", "libvorbis", "-q", str(audio_quality_vorbis), job.dest],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            elif audio_format == "mp3":
                processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                "-c", "libmp3lame", "-q", str(audio_quality_lame), job.dest],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            elif audio_format == "opus":
                #use ffmpeg instead of opusenc for preventing the application of R128 gain, making replaygain work as expected
                processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                "-c", "libopus", "-b", str(audio_quality_opus), job.dest],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            if platform == "windows":
                while len(processes) >= threads:
                    time.sleep(.1) #for windows compatibility
                    processes.difference_update([p for p in processes if p.poll() is not None])
            else:
                if len(processes) >= threads:
                    os.wait()
                    processes.difference_update([p for p in processes if p.poll() is not None])
        done += len(transcode_jobs[list])
        logger.info("Encoded " + str(done) + "/" + str(transcode_jobs_size) + " files (" + str(int(100 * done / transcode_jobs_size)) + "%).")

# Copy image files (jpg,png,gif) to destination
if copy_album_art:
    logger.info("Start Copying album art now.")
    for folder in folders:
        for file in os.listdir(folder):
            if file.endswith(".jpg") or file.endswith(".png") or file.endswith(".gif"):
                image_src = os.path.join(folder,file)
                image_dest = os.path.join(folders[folder],file)
                added_files.add(image_dest)
                if not os.path.isfile(image_dest):
                    shutil.copy(image_src,image_dest)
                    logger.debug("Copying album art: " + image_dest)
                else:
                    logger.debug("Album art exists: " + image_dest)

# Remove files from destination that are not in playlist any more
if delete_non_existent:
    logger.info("Start removing files now.")
    dest_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(dest_dir) for f in filenames]
    for f in dest_files:
        if not f in added_files:
            logger.debug("File " + f + " is not in playlist any more. Removing it.")
            os.remove(f)
    # Remove potential empty directories after deleting stuff.
    remove_empty_dirs(dest_dir)

logger.info("Finished playlist synchronization.")
