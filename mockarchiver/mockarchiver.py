import os
import os.path
import sys
import logging
import argparse
import uvicorn
import time
import threading
import fusefs
import contextlib

from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Response, status

"""
This mocks the LTS archiver.  The idea is clients use it as they would
use the real archiver,

Config (.env file):
    FINAL_DIR: directory (relative to this module) where you copy files
               to in order to initiate archiving
    REPLICA_DIR: directory (relative to this module) where LTS
                 (and this mock) copy the file to in order to replicate it
    PORT to serve the REST API
    LOOP_SLEEP_SECS: this script polls the FINAL_DIR directory.  Sleep
                     for this number of seconds between polling loops
    ARCHIVE_DELAY_SECS:  to mock real archiving time delay, sleep this 
                         number of seconds after (un)archiving a file
    FUSER: command to execute fuser.  For running on bare metal, probably
           /usr/bin/fuser.  For running on docker, 
           ssh YOUR_HOST_USERNAME@host.docker.internal /usr/bin/fuser

REST API
    /delete/filename: delete the file from the archive
    /exit: quit

REQUIREMENTS
    Needs libfuse (Linux) or MacFuse.  Also theoretically one available
    for Windows.
    Mac:  install --cask macfuse

"""
script_path = os.path.dirname(os.path.abspath(__file__))
parser = argparse.ArgumentParser(
    prog='import_words',
    description='Load words from Excel sheets into DB',
)
parser.add_argument("-e", "--envfile", nargs=1, default=".env")
parser.add_argument("-d", "--debug", action='store_true')
args = parser.parse_args()

load_dotenv(args.envfile)

FINAL_DIR=os.getenv("FINAL_DIR", "../lts/final")
REAL_FINAL_DIR=FINAL_DIR + ".real"
REPLICA_DIR=os.getenv("REPLICA_DIR", "../lts/replica")
PORT=int(os.getenv("PORT", "7000"))
LOOP_SLEEP_SECS=int(os.getenv("LOOP_SLEEP_SECS", "5"))
ARCHIVE_DELAY_SECS=int(os.getenv("ARCHIVE_DELAY_SECS", "5"))
FUSER=os.getenv("FUSER", "/usr/bin/fuser")

def fmt_filter(record):
    record.levelname = '%s:' % record.levelname
    return True

level = logging.INFO
if (args.debug):
    level = logging.DEBUG
logging.basicConfig(level=level, 
                    format='\x1b[32m%(levelname)-8s\033[0m  %(message)s')
logger = logging.getLogger()
logger.addFilter(fmt_filter)

def deleteFile(filename : str, delete_real=False):
    """
    Delete the named file from all places associated with the LTS.
    Called as a REST endpoint and also called for all files upon start.
    """
    dirs = [FINAL_DIR, REPLICA_DIR]
    if (delete_real):
        dirs.append(REAL_FINAL_DIR)
    for path in dirs:
        fullpath = os.path.join(path, filename)
        if (os.path.isfile(fullpath)):
            try:
                os.remove(fullpath)
            except:
                logging.warn("Couldn't delete " + fullpath)

def deleteAllFiles():
    """
    Delete all files from the LTS.  We do this on startup as the FUSE FS
    we built doesn't cope to well with pre-existing files
    """
    files = [f for f in os.listdir(REAL_FINAL_DIR) 
                if os.path.isfile(os.path.join(REAL_FINAL_DIR,f))]
    for file in files:
        deleteFile(file, delete_real=True)

def delayed_exit():
    """
    Just sleeps one second before exiting.  This is so it can be called from
    a REST endpoint and not return an error.
    """
    time.sleep(1)
    print("Exiting")
    sys.exit(0)

class UvicornServer(uvicorn.Server):
    """
    This class is for starting Uvicorn in a thread that can be exited
    when Ctrl-C is pressed or sys.exit() is called
    """
    def install_signal_handlers(self):
        pass

    @contextlib.contextmanager
    def run_in_thread(self):
        thread = threading.Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()

#############################################################
# REST API

app = FastAPI()

@app.get("/delete/{filename}")
async def delete(filename : str, response: Response):
    '''Delete the named file from the archiver'''
    deleteFile(filename)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None

@app.get("/exit")
async def exit(response: Response):
    '''Exit the application'''
    response.status_code = status.HTTP_204_NO_CONTENT
    thread = threading.Thread(target=delayed_exit,
                              name = "exit")
    thread.start()
    return None

if __name__ == "__main__":
    deleteAllFiles()
    config = uvicorn.Config(app, port=PORT, log_level="info")
    server = UvicornServer(config=config)
    with server.run_in_thread():
        # Uvicorn started.
        fusefs.start(FINAL_DIR, REAL_FINAL_DIR, REPLICA_DIR, 
                     ARCHIVE_DELAY_SECS)
    # Uvicorn stopped.
    sys.exit(0);