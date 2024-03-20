from pyscript import document
from js import console, window, selectedFiles, filesForUpload
import js

from pyscript import display

# import hyperspy
import zipfile
import json
import os
import time


def extract_metadata(event):
    list = document.querySelector("#list")
    output_div = document.querySelector("#output")
    display(filesForUpload.length)

    root = "/home/wiphilip/Documents/coding/testdata"

    for f in filesForUpload:
        display(os.path.join(root, f.name))

    num = 0
    t0 = time.time()
    for i in range(10**8):
        num = num + 1
    t1 = time.time()
    display(t1 - t0)
