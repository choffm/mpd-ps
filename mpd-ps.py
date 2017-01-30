#!/usr/bin/python3

import argparse
import configparser
import logging
import multiprocessing
import os
import platform
import re
import shutil
import subprocess
import time

from mpd import MPDClient
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

__author__ = 'Clemens Hoffmann [clemens [at] vibee.de]'


class MpdPs:
    @staticmethod
    def get_current_time():
        return round(time.time() * 1000)

    class TranscodingJob:
        def __init__(self, src, dest):
            self.src = src
            self.dest = dest

    # Bottom-Up removal of all empty directories in path
    def remove_empty_dirs(self, path):
        for dirpath, dirnames, filenames in os.walk(path, topdown=False):
            if len(filenames) == 0 and len(dirnames) == 0:
                self.logger.debug(dirpath + " is empty. Deleting empty "
                                            "directory.")
                os.rmdir(dirpath)

    # Copy image files (jpg,png,gif) to destination
    def copy_album_art(self, added_files, folders):
        self.logger.info("Start Copying album art now.")
        for folder in folders:
            for file in os.listdir(folder):
                if file.endswith(".jpg") or file.endswith(
                        ".png") or file.endswith(".gif"):
                    image_src = os.path.join(folder, file)
                    image_dest = os.path.join(folders[folder], file)
                    added_files.add(image_dest)
                    if not os.path.isfile(image_dest):
                        shutil.copy(image_src, image_dest)
                        self.logger.debug("Copying album art: " + image_dest)
                    else:
                        self.logger.debug("Album art exists: " + image_dest)

    # Remove files from destination that are not in playlist any more
    def delete_non_existant(self, added_files):
        self.logger.info("Start removing files now.")
        dest_files = [os.path.join(dp, f) for dp, dn, filenames in
                      os.walk(self.dest_dir)
                      for f in filenames]
        for f in dest_files:
            if f not in added_files:
                self.logger.debug(
                    "File " + f + " is not in playlist any more. Removing it.")
                os.remove(f)
        # Remove potential empty directories after deleting stuff.
        self.remove_empty_dirs(self.dest_dir)

    def __init__(self, config_file=None):
        self.config_file = config_file
        self.host = "localhost"
        self.port = ""
        self.password = ""
        self.mpd_root_dir = ""
        self.dest_dir = ""
        self.audio_format = "opus"
        self.threads = 8
        self.verbose = False
        self.will_delete_non_existent = False
        self.will_copy_album_art = True
        self.transcode_flac = True
        self.transcode_mp3 = False
        self.transcode_m4a = False
        self.transcode_m4a_threshold = 200000
        self.transcode_mp3_threshold = 200000
        self.audio_quality_lame = 3
        self.audio_quality_opus = 96000
        self.audio_quality_vorbis = 4
        self.logger = logging.getLogger("mpd-ps")
        self.mpd_playlist = None

    def parse_config_file(self):
        if not self.config_file:
            if os.path.exists("mpd-ps.conf"):
                self.config_file = os.path.join("mpd-ps.conf")
            elif platform == "windows":
                self.config_file = os.path.join(os.getenv("APPDATA"), "mpd-ps",
                                                "mpd-ps.conf")
            else:
                self.config_file = os.path.join(os.path.expanduser("~"),
                                                ".config", "mpd-ps",
                                                "mpd-ps.conf")
        config_parser = configparser.RawConfigParser()
        config_parser.read(self.config_file)
        if os.path.exists(self.config_file):
            if config_parser.has_section('Host'):
                if config_parser.has_option('Host', 'host'):
                    self.host = config_parser.get('Host', 'host')
                if config_parser.has_option('Host', 'port'):
                    self.port = config_parser.get('Host', 'port')
                if config_parser.has_option('Host', 'password'):
                    self.password = config_parser.get('Host', 'password')
            if config_parser.has_section('General'):
                if config_parser.has_option('General', 'src'):
                    self.mpd_root_dir = config_parser.get('General', 'src')
                if config_parser.has_option('General', 'dest'):
                    self.dest_dir = config_parser.get('General', 'dest')
                if config_parser.has_option('General', 'audio_format'):
                    self.audio_format = config_parser.get('General',
                                                          'audio_format')
                if config_parser.has_option('General', 'transcode_flac'):
                    self.transcode_flac = config_parser.getboolean('General',
                                                                   'transcode_flac')
                if config_parser.has_option('General', 'threads'):
                    self.threads = config_parser.getint('General', 'threads')
                if config_parser.has_option('General', 'verbose'):
                    self.verbose = config_parser.getboolean('General',
                                                            'verbose')
                if config_parser.has_option('General', 'delete_non_existent'):
                    self.will_delete_non_existent = config_parser.getboolean(
                        'General',
                        'delete_non_existent')
                if config_parser.has_option('General', 'copy_album_art'):
                    self.will_copy_album_art = config_parser.getboolean(
                        'General', 'copy_album_art')
                if config_parser.has_option('General', 'transcode_m4a'):
                    self.transcode_m4a = config_parser.getboolean('General',
                                                                  'transcode_m4a')
                if config_parser.has_option('General',
                                            'transcode_m4a_threshold'):
                    self.transcode_m4a_threshold = config_parser.getint(
                        'General',
                        'transcode_m4a_threshold')
                if config_parser.has_option('General', 'transcode_mp3'):
                    self.transcode_mp3 = config_parser.getboolean('General',
                                                                  'transcode_mp3')
                if config_parser.has_option('General',
                                            'transcode_mp3_threshold'):
                    self.transcode_mp3_threshold = config_parser.getint(
                        'General',
                        'transcode_mp3_threshold')
                if config_parser.has_option('General',
                                            'audio_quality_lame'):  # 0 - 10,
                    self.audio_quality_lame = config_parser.getint('General',
                                                                   'audio_quality_lame')
                if config_parser.has_option('General',
                                            'audio_quality_vorbis'):  # -1..10, fractions
                    # allowed
                    self.audio_quality_vorbis = config_parser.getfloat(
                        'General',
                        'audio_quality_vorbis')
                if config_parser.has_option('General',
                                            'audio_quality_opus'):  # in bit/s
                    self.audio_quality_opus = config_parser.getint('General',
                                                                   'audio_quality_opus')
        else:
            self.logger.error(
                "Config file not found. Config file has to be places in the "
                "same folder as this script or in "
                "$HOME/.conf/mpd-ps/mpd-ps.conf or to be specified by using "
                "the --config [PATH_TO_CONF] switch.")
            exit(-1)

        if self.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        if os.path.exists(self.config_file):
            self.logger.info('Using configuration file: ' + self.config_file)
        else:
            self.logger.error(
                'Configuration file ' + self.config_file + " doesn't not "
                                                           "exist. "
                                                           "Aborting.")
            exit(-1)

        if not self.mpd_root_dir:
            self.logger.error(
                "Please specify the root folder of mpd server within config "
                "file (src).")
            exit(-1)

        if not self.dest_dir:
            self.logger.error(
                "Please specify the destination folder within config file "
                "(dest).")
            exit(-1)

        if self.audio_format == "":
            self.audio_format = "opus"
        elif self.audio_format != "ogg" and self.audio_format != "mp3" and \
                        self.audio_format != "opus":
            self.logger.error(
                "Bad audio format. mpd-ps supports ogg, opus and mp3.")
            exit(-1)

        if not self.transcode_flac:
            self.logger.warn(
                "Copying FLAC files instead of transcoding. Specified audio "
                "format settings is ignored.")

        if not self.host:
            self.host = "localhost"

        if not self.port:
            self.port = 6600

        if not self.password:
            self.password = ""

        if not self.threads or self.threads <= 0:
            self.threads = multiprocessing.cpu_count()

        self.logger.info('Host: ' + self.host + ":" + str(self.port))
        self.logger.info('MPD music folder: ' + self.mpd_root_dir)
        self.logger.info('Destination folder: ' + self.dest_dir)
        self.logger.info(
            'FLAC files:' + 'transcode to ' + self.audio_format if
            self.transcode_flac else 'copy')
        self.logger.info(
            'MP3 files:' + 'transcode to ' + self.audio_format + ' if bitrate > ' + str(
                self.transcode_mp3_threshold / 1000) + 'kbit/s' if
            self.transcode_mp3 else 'copy')
        self.logger.info(
            'M4A files:' + 'transcode to ' + self.audio_format + ' if bitrate > ' + str(
                self.transcode_m4a_threshold / 1000) + 'kbit/s' if
            self.transcode_m4a else 'copy')
        self.logger.info('Transcoder threads: ' + str(self.threads))

    def get_mpd_playlist(self):
        client = MPDClient()
        client.timeout = 10
        client.idletimeout = None  # timeout for fetching the result of the idle
        # command is handled separately, default: None
        client.connect(self.host, self.port)  # connect to localhost:6600
        client.password(self.password)

        self.mpd_playlist = client.playlist()  # print the MPD version
        client.close()  # send the close command
        client.disconnect()  # disconnect from the server

    def sync_plalist(self):
        transcode_jobs = {}
        transcode_jobs_size = 0
        size = 0
        mytime = 0
        added_files = set()
        folders = {}
        count = 0
        item_size = 0

        # Start the sync
        for item in self.mpd_playlist:
            if item_size % 10 == 0:
                self.logger.info("Processed " + str(item_size) + "/" + str(
                    len(self.mpd_playlist)) + " files (" + str(
                    int(100 * item_size / len(self.mpd_playlist))) + "%).")
            src_relative_name = item[6:]
            src_relativ_path = os.path.dirname(src_relative_name)
            src_absolute_name = os.path.join(self.mpd_root_dir,
                                             src_relative_name)
            src_absolute_path = os.path.dirname(src_absolute_name)

            dest_absolute_name = os.path.join(self.dest_dir,
                                              src_relative_name)
            dest_absolute_path = os.path.dirname(dest_absolute_name)

            transcode_file = False
            if src_absolute_name.endswith(".flac") and self.transcode_flac:
                transcode_file = True
                dest_absolute_name = re.sub(r".m4a$", "." + self.audio_format,
                                            dest_absolute_name)
                dest_absolute_name = re.sub(r".flac$", "." + self.audio_format,
                                            dest_absolute_name)

            if src_absolute_name.endswith(".mp3") and self.transcode_mp3:
                audio = MP3(src_absolute_name)
                if audio.info.bitrate >= self.transcode_mp3_threshold:
                    transcode_file = True
                    dest_absolute_name = re.sub(r".mp3$",
                                                "." + self.audio_format,
                                                dest_absolute_name)

            if src_absolute_name.endswith(".m4a") and self.transcode_m4a:
                audio = MP4(src_absolute_name)
                if audio.info.bitrate >= self.transcode_m4a_threshold:
                    transcode_file = True
                    dest_absolute_name = re.sub(r".m4a$",
                                                "." + self.audio_format,
                                                dest_absolute_name)

            folders[src_absolute_path] = dest_absolute_path
            item_size += 1
            # Skip existing files
            if os.path.isfile(dest_absolute_name) and os.path.getsize(
                    dest_absolute_name) == os.path.getsize(src_absolute_name):
                self.logger.debug(
                    "file " + dest_absolute_name + " exists. Skipping.")
                added_files.add(dest_absolute_name)
                continue

            # Create directories on destination, if they don't exist
            elif not os.path.exists(dest_absolute_path):
                os.makedirs(dest_absolute_path)

            # Add file to transcode jobs dict if specified
            if transcode_file:
                if dest_absolute_name not in added_files:
                    added_files.add(dest_absolute_name)
                    if not os.path.exists(dest_absolute_name):
                        if src_relativ_path in transcode_jobs:
                            transcode_jobs[src_relativ_path].append(
                                self.TranscodingJob(src_absolute_name,
                                                    dest_absolute_name))
                            transcode_jobs_size += 1
                        else:
                            transcode_jobs[src_relativ_path] = []
                            transcode_jobs[src_relativ_path].append(
                                self.TranscodingJob(src_absolute_name,
                                                    dest_absolute_name))
                            transcode_jobs_size += 1
                    else:
                        self.logger.debug(
                            "Transcoded file exists: %s", dest_absolute_name)
                else:
                    self.logger.debug("Duplicate playlist item ignored: %s",
                                      dest_absolute_name)

            # Copy all other audio files directly to destination
            else:
                added_files.add(dest_absolute_name)
                cur_time = self.get_current_time()
                try:
                    shutil.copy(src_absolute_name, dest_absolute_name)
                    count += 1
                    self.logger.debug("Copied file to: " + dest_absolute_name)

                    mytime += (self.get_current_time() - cur_time) / 1000
                    size += os.path.getsize(dest_absolute_name) / (1024 * 1024)
                    if mytime != 0:
                        self.logger.debug(
                            "Transferred " + str(count) + " files with " + str(
                                size / mytime)[:str(size / mytime).find(
                                ".") + 3] + "MB/s")
                except OSError:
                    self.logger.error(
                        "Copying " + src_absolute_name + " to " +
                        dest_absolute_name + " failed. Skipping file.")

        self.logger.info(
            "Transferred " + str(size)[:str(size).find(".") + 3] + " MB.")

        if transcode_jobs:
            self.logger.info("Start transcoding audio files now.")
            done = 0
            processes = set()
            for folder in transcode_jobs:
                for job in transcode_jobs[folder]:
                    self.logger.debug("Encoding file:" + job.dest)
                    if self.audio_format == "ogg":
                        processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                        "-c", "libvorbis", "-q",
                                                        str(
                                                            self.audio_quality_vorbis),
                                                        job.dest],
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE))
                    elif self.audio_format == "mp3":
                        processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                        "-c", "libmp3lame",
                                                        "-q",
                                                        str(
                                                            self.audio_quality_lame),
                                                        job.dest],
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE))
                    elif self.audio_format == "opus":
                        processes.add(subprocess.Popen(["ffmpeg", "-i", job.src,
                                                        "-c", "libopus", "-b",
                                                        str(
                                                            self.audio_quality_opus),
                                                        job.dest],
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE))
                    if platform == "windows":
                        while len(processes) >= self.threads:
                            time.sleep(.1)  # for windows compatibility
                            processes.difference_update(
                                [p for p in processes if p.poll() is not None])
                    else:
                        if len(processes) >= self.threads:
                            os.wait()
                            processes.difference_update(
                                [p for p in processes if p.poll() is not None])
                done += len(transcode_jobs[folder])
                self.logger.info("Encoded " + str(done) + "/" + str(
                    transcode_jobs_size) + " files (" + str(
                    int(100 * done / transcode_jobs_size)) + "%).")
        if self.will_copy_album_art:
            self.copy_album_art(added_files, folders)
        if self.will_delete_non_existent:
            self.delete_non_existant(added_files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    platform = platform.system().lower()
    parser.add_argument("--config", help="specify path to config "
                                         "file.", dest="config")
    args = parser.parse_args()
    mpd_ps = MpdPs(args.config)
    mpd_ps.parse_config_file()
    mpd_ps.get_mpd_playlist()
    mpd_ps.sync_plalist()
