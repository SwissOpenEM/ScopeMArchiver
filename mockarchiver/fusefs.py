#!/usr/bin/env python
import logging
import os
import os.path
import shutil
import time
import subprocess
import fcntl
import threading
import time
import datetime

from errno import EACCES, EIO
from os.path import realpath
from threading import Lock
from pathlib import Path
from dotenv import load_dotenv

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

"""
This module contains a filesystem implemented using FUSE so that we can
intercept the reads and writes, emulating what LTS would do.
"""

class Loopback(LoggingMixIn, Operations):
    """
    Unplements the final firectory as a Fuse filesystem, so that we 
    can catch the read and writes and perform necessary operations.

    Based on https://github.com/fusepy/fusepy/blob/master/examples/loopback.py
    """

    def archiver(self, filename: str):
        """
        Started in a thread to archive a single file to tape.
        It copies it to the replica directory, waits the defined number
        of seconds, then sets the sticky bit on the replica, as LTS would do.
        """
        logging.info("Archive " + filename)
        final_file = os.path.join(self.root, filename)
        replica_file = os.path.join(self.replica_dir, filename)
        shutil.copyfile(final_file, replica_file)
        if (self.archive_delay_secs > 0):
            time.sleep(self.archive_delay_secs)
        os.chmod(replica_file, 0o1644)   
        logging.info("Archived " + filename)

    def unarchiver(self, filename : str):
        """
        Started in a thread to unarchive a single file from tape.
        It adds it to the unarchiving list, sleeps, removes it from
        the unarchiving list and clears the sticky bit
        """
        logging.info("Unarchive " + filename)
        replica_file = os.path.join(self.replica_dir, filename)
        self.unarchiving_files.add(filename)
        if (self.archive_delay_secs > 0):
            time.sleep(self.archive_delay_secs)
        os.chmod(replica_file, 0o644)   
        self.unarchiving_files.remove(filename)
        logging.info("Unarchived " + filename)

    def __init__(self, root, replica_dir, 
                 archive_delay_secs,):
        self.root = realpath(root)
        self.replica_dir = replica_dir
        self.archive_delay_secs = archive_delay_secs
        self.unarchiving_files = set()
        self.rwlock = Lock()

    def __call__(self, op, path, *args):
        return super(Loopback, self).__call__(op, self.root + path, *args)
        
    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    chmod = os.chmod
    chown = os.chown

    def create(self, path, mode):
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        if datasync != 0:
            return os.fdatasync(fh)
        else:
            return os.fsync(fh)

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        return dict((key, getattr(st, key)) for key in (
            'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime',
            'st_nlink', 'st_size', 'st_uid'))

    getxattr = None

    def link(self, target, source):
        return os.link(self.root + source, target)

    listxattr = None
    mkdir = os.mkdir
    mknod = os.mknod
    
    def open(self, path, flags):
        """
        Because files may be cached, we don't intercept the read operation
        to trigger unarchiving.  Instead we intercept this.
        If there is a read and the file is archived (in the replica folder
        with the sticky bit set, initially return an IO error.  After the
        defined number of seconds have elapsed, we consider it to have been
        fetched back from tape, we unset the sticky bit and open returns the 
        file descriptor as it should.)
        """
        fd = os.open(path, flags)
        statusbits = fcntl.fcntl(fd, fcntl.F_GETFL)
        basename = os.path.basename(path)
        replica_file = os.path.join(self.replica_dir, basename)
        if (statusbits & 1 == 0 and os.path.isfile(replica_file)):
            if (os.stat(replica_file).st_mode & 0o1000 == 0o1000):
                # open for reading and file has been archived
                if (basename not in self.unarchiving_files):
                    # archiving has not started - start it
                    thread = threading.Thread(target=self.unarchiver, 
                                                name="Unarchive_"+basename,
                                                args=(basename,))
                    thread.start()
                    raise FuseOSError(EIO)
                elif basename in (self.unarchiving_files):
                    # archiving has started but not finished
                    raise FuseOSError(EIO)
        return fd

    def read(self, path, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.read(fh, size)

    def readdir(self, path, fh):
        return ['.', '..'] + os.listdir(path)

    readlink = os.readlink

    def release(self, path, fh):
        """
        If this was a write operation, initiate archiving.  We assume
        that a write is only ever done once (this module cleans up on
        restart anyway).
        To initiate archival, start archiver() in a thread.  It will
        copy the file to the replica directory. wait the given number of
        seconds, then set the sticky bit on it, as LTS would.
        """
        statusbits = fcntl.fcntl(fh, fcntl.F_GETFL)
        ret =  os.close(fh)
        if (statusbits & 1 == 1):
            filename = os.path.basename(path)
            thread = threading.Thread(target=self.archiver, 
                                        name="Archive_"+filename,
                                        args=(filename,))
            thread.start()


    def rename(self, old, new):
        return os.rename(old, self.root + new)

    rmdir = os.rmdir

    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in (
            'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail',
            'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax'))

    def symlink(self, target, source):
        return os.symlink(source, target)

    def truncate(self, path, length, fh=None):
        with open(path, 'r+') as f:
            f.truncate(length)

    unlink = os.unlink
    utimens = os.utime

    def write(self, path, data, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.write(fh, data)

def start(final_dir : str, real_final_dir : str, 
          replica_dir : str, archive_delay_secs: int):
    """
    Starts the FUSE fs in the foreground.  First forced an umount of the
    mount directory in case it exited badly before.
    """
    umount(real_final_dir)
    fuse = FUSE(
                Loopback(real_final_dir, replica_dir, 
                         archive_delay_secs), 
                 final_dir, foreground=True, allow_other=True)

def umount(dir : str):
    """
    Force unmount of the FUSE directory.  This is in case this script
    exited badly.
    """
    cmd = ['umount ', '-f', dir]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout.read()
        stdout, stderr = proc.communicate()
    except:
        pass

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('mount')
    parser.add_argument("-e", "--envfile", nargs=1, default=".env")
    parser.add_argument("-d", "--debug", action='store_true')
    args = parser.parse_args()

    load_dotenv(args.envfile)

    FINAL_DIR=os.getenv("FINAL_DIR", "../lts/final")
    REAL_FINAL_DIR=os.getenv("FINAL_DIR", "../lts/final.real")
    FILES_DIR=os.path.join(FINAL_DIR + ".files")
    REPLICA_DIR=os.getenv("REPLICA_DIR", "../lts/replica")
    PORT=int(os.getenv("PORT", "7000"))
    LOOP_SLEEP_SECS=int(os.getenv("LOOP_SLEEP_SECS", "5"))
    ARCHIVE_DELAY_SECS=int(os.getenv("ARCHIVE_DELAY_SECS", "5"))
    UNARCHIVE_DELAY_SECS=int(os.getenv("ARCHIVE_DELAY_SECS", "5"))
    FUSER=os.getenv("FUSER", "/usr/bin/fuser")

    logging.basicConfig(level=logging.INFO)
    umount(REAL_FINAL_DIR)
    fuse = FUSE(
                Loopback(args.root, REPLICA_DIR, 
                         ARCHIVE_DELAY_SECS, UNARCHIVE_DELAY_SECS), 
                 args.mount, foreground=True, allow_other=True)
