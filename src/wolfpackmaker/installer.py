
from argparse import ArgumentParser
from requests import Session
from rich import inspect
from util import Log
import logging

class Installer:
    def __init__(self):
        self.parser = ArgumentParser(
            description='Wolfpackmaker / installer.py'
        )
        self.parser.add_argument('-r', '--repo', help='Wolfpack modpack repository from https://git.kalka.io e.g'
                                                '--repo Odin, from https://git.kalka.io/Wolfpack/Odin')
        self.parser.add_argument("-v", "--verbose", action="store_true",
                            help="increase output verbosity")
        self.args = self.parser.parse_args()
        self.session = Session()
        self.c = Log()
    
    def server_install(self):
        self.repo = self.args.repo
        self.c.info("Installing serverside...")


    


def main():
    i = Installer()
    i.c.parse_log(i.args)
    i.c.fancy_intro(i.parser.description)
    i.server_install()
    i.c.save_log("installer")


main()

