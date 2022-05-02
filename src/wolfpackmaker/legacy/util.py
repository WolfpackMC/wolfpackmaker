
from posixpath import basename, dirname
from rich.console import Console
import logging
import time
from rich import inspect
from appdirs import user_cache_dir
import datetime
from dateutil import tz
from os import mkdir
import random

import owoify
from pyfiglet import Figlet



class Log(Console):
    log_contents = {}
    f = Figlet()

    def warn(self, msg):
        logging.root.level <= logging.WARN and self.log(f"[yellow][WARN][white] {msg}")
    def warning(self, msg):
        self.warn(msg)
    def info(self, msg):
        logging.root.level <= logging.INFO and self.log(f"[cyan][INFO][white] {msg}")
    def debug(self, msg):
        logging.root.level <= logging.DEBUG and self.log(f"[green][DEBUG][white] {msg}")
    def critical(self, msg):
        logging.root.level <= logging.CRITICAL and self.log(f"[red][CRITICAL][white] {msg}")

    def log(self, msg):
        super().log(msg)
        t = time.time()
        self.log_contents[t] = msg
    
    def parse_log(self, args):
        if args.verbose:
            logging.root.level = logging.DEBUG
            self.debug("Enabling verbose mode.")
        else:
            logging.root.level = logging.INFO

    def fancy_intro(self, description=''):
        self.info(str('').join(['####' for _ in range(16)]))
        self.info(self.f.renderText(("woofmc.xyz")))
        keywords = random.choice(
            ['A custom made Minecraft modpack script. Nothing special, hehe.',
            'Please don\'t tell anyone about this...',
            'Hehe. UwU, It\'s all we have, I know. I\'m sorry!',
            'I should probably get a better idea for this list...',
            'Not sponsored by Awoos!'
            ]
        )
        self.info(owoify.owoify(keywords))
        self.info(description)
        self.info(str('').join(['####' for _ in range(16)]))

    def save_log(self, module):
        self.log_cache = user_cache_dir(f'wolfpackmaker/log/{module}')
        try:
            mkdir(self.log_cache)
        except FileNotFoundError:
            try:
                mkdir(dirname(self.log_cache))
            except FileNotFoundError:
                mkdir(dirname(dirname(self.log_cache)))
        except FileExistsError:
            pass
        finally:
            try:
                mkdir(self.log_cache)
            except FileNotFoundError as e:
                self.warn(f"Could not save logfile {self.log_cache} with the error {e}.")
                return
            except FileExistsError:
                pass
        self.debug("Saving log...")
        tzinfo = tz.gettz('EDT')
        logfile_time = datetime.datetime.fromtimestamp(time.time(), tz=tzinfo)
        logfile_date = datetime.datetime.strftime(logfile_time, "%m_%d_%Y-%H_%M_%S")
        with open(f"{self.log_cache}/{logfile_date}.log", "w") as f:
            for k, v in self.log_contents.items():
                format_time = datetime.datetime.fromtimestamp(k, tz=tzinfo)
                format_date = datetime.datetime.strftime(format_time, "%m-%d-%Y-%H:%M:%S")
                f.write(f"[{format_date}] {v}\n")

