#!/usr/bin/env python3
import os
import platform
import shutil
import tempfile
import webbrowser
from configparser import ConfigParser
from pathlib import Path
from subprocess import run

import pyperclip
import requests
from PIL import Image


class Configuration():
    def __init__(self):
        config_parser = ConfigParser()
        config_parser.read_dict(
            {
                "Myazo": {
                    "gyazo_server": False,  # If True, upload_script and secret are ignored
                    "gyazo_direct_link": True,  # Ignored if gyazo_server is False
                    "upload_script": "https://myazo.example.com/upload.php",
                    "secret": "hunter2",
                    "clear_metadata": True,
                    "open_browser": True,
                    "copy_clipboard": True,
                    "output_url": True,
                }
            }
        )
        config_parser.read(os.path.expanduser("~/.config/myazo/config.ini"))
        self.config = config_parser["Myazo"]

    def get_backend(self, system, tmp_filename):
        backends = {
            "Linux": {
                "gnome-screenshot": ["-a", "-f", tmp_filename],
                "mv": ["$(xfce4-screenshooter -r -o ls)", tmp_filename],
                # KDE Spectacle requires slight user interaction after selecting region
                "spectacle": ["-b", "-n", "-r", "-o", tmp_filename],
                "scrot": ["-s", tmp_filename],
                # ImageMagick
                "import": [tmp_filename],
            },
            # macOS
            "Darwin": {"screencapture": ["-i", tmp_filename]},
            # '/clip' requires at least Win10 1703
            "Windows": {"snippingtool": ["/clip"]},
        }
        util = None
        for util, args in backends[system].items():
            if shutil.which(util) is not None and run([util] + args).returncode == 0:
                break
        return util


class Myazo:
    def __init__(self):
        c = Configuration()
        self.tmp_filename = tempfile.NamedTemporaryFile(suffix=".png").name
        self.conf = c.config
        self.backend = c.get_backend(platform.system(), self.tmp_filename)

    def take_screenshot(self):

        if self.backend == "snippingtool":
            from PIL import ImageGrab

            img = ImageGrab.grabclipboard()
            if img is not None:
                img.save(self.tmp_filename, optimize=True)

        if os.path.isfile(self.tmp_filename) is not True:
            print("Error: Failed to take screenshot.")
            exit(1)

        if self.conf.getboolean("clear_metadata"):
            img = Image.open(self.tmp_filename)
            new_img = Image.new(img.mode, img.size)
            new_img.putdata(list(img.getdata()))
            new_img.save(self.tmp_filename, optimize=True)

        # Upload image to server
        img = open(self.tmp_filename, "rb")

        if self.conf.getboolean("gyazo_server"):
            r = requests.post("https://upload.gyazo.com/upload.cgi", files={"imagedata": img})
        else:
            r = requests.post(
                self.conf.get("upload_script"),
                data={"secret": self.conf.get("secret")},
                files={"screenshot": img},
            )

        if r.status_code != 200:
            print(
                "Error: Failed to upload screenshot. "
                f"Server returned status code '{r.status_code}'."
            )
            exit(2)

        if self.conf.getboolean("gyazo_server") and self.conf.getboolean("gyazo_direct_link"):
            # Convert the Gyazo link to a direct image
            # https://gyazo.com/hash > https://i.gyazo.com/hash.extension
            url = r.text.replace("//", "//i.") + Path(self.tmp_filename).suffix
        else:
            url = r.text

        if self.conf.getboolean("open_browser"):
            webbrowser.open(url)
        if self.conf.getboolean("copy_clipboard"):
            pyperclip.copy(url)
        if self.conf.getboolean("output_url"):
            print(url)

        img.close()
        os.remove(self.tmp_filename)
