#!/usr/bin/env python3

import argparse
import asyncio
import io
import json
import platform
import shutil
import sys
import requests
import zipfile
from appdirs import user_cache_dir
from os import getcwd, listdir, remove
from os.path import abspath, dirname, exists, join, getsize
from pathlib import Path
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.table import Column
from rich.traceback import install as init_traceback
from util import Log


class Wolfpackmaker:
    VERSION = '1.0.0'
    log = Log()

    def main(self):
        self.init_args()
        self.parse_args()
        self.log.parse_log(self.args)

        self.repo_info = {
            'user': "WolfpackMC",
            'repo': self.args.repo,
            'github_api': "https://api.github.com/repos/{}/{}/releases",
            'github_files': ['manifest.lock', 'config.zip']
        }

        self.headers = {
            'User-Agent': 'Wolfpackmaker (https://woofmc.xyz)',
            'Accept-Encoding': None
        }

        self.meme_activated = True

        self.macos_incompatible_mods = [
            "itlt"
        ]

        self.assemble_directories()

        self.download_count = [0]

        self.to_process = []  # mods to process
        self.to_copy_process = [] # mods to copy

        self.session = requests.Session()
        self.session.headers.update(self.headers)


    def parse_args(self):
        self.args = self.parser.parse_args()


    def init_args(self):
        self.parser = argparse.ArgumentParser(
            description='Wolfpackmaker (https://woofmc.xyz)'
        )
        self.parser.add_argument('-v', '--verbose', help='Increase output verbosity.', action='store_true')
        self.parser.add_argument('-r', '--repo', help='Wolfpack modpack repository from https://github.com/WolfpackMC e.g'
                                                '--repo Wolfpack-Odin, from https://git.kalka.io/WolfpackMC/Wolfpack-Odin')
        self.parser.add_argument('-mmc', '--multimc', help='Enable MultiMC setup.', action='store_true')
        self.parser.add_argument('-mc', '--minecraft-dir', help='Specify custom minecraft dir. Defaults to .minecraft', default='.minecraft')
        self.parser.add_argument('-d', '--download', help='Custom download directory')
        self.parser.add_argument('--cache', help='Custom cache directory')
        self.parser.add_argument('-c', '--clientonly', help='Enable clientonly.', action='store_true', default=False)
        self.parser.add_argument('-s', '--serveronly', help='Enable serveronly.', action='store_true', default=False)
        self.parser.add_argument('-t', '--test', help='Test mode only Does not save any mod jars.', action='store_true', default=False)
        self.parser.add_argument('-rs', '--release', help='Get release name.', default='latest')
        self.parser.add_argument('--dir', help=f'Custom directory for Wolfpackmaker. Defaults to {dirname(getcwd())}')
    
    def assemble_directories(self):
        self.current_dir = self.args.dir and self.args.dir or dirname(getcwd())
        self.parent_dir = dirname(self.current_dir)
        self.cached_dir = user_cache_dir('wolfpackmaker')
        self.minecraft_dir = join(self.current_dir, self.args.minecraft_dir)

        self.mods_dir = self.args.download and join(self.current_dir, self.args.download) or join(self.minecraft_dir, 'mods')

        self.mods_cache_dir = self.args.cache and join(self.current_dir, self.args.cache) or join(self.cached_dir, 'mods')

        self.resourcepack_dir = join(self.minecraft_dir, 'resourcepacks')
        self.config_dir = join(self.minecraft_dir, 'config')
        self.mods_cached = join(self.cached_dir, '.cached_mods.json')
        self.modpack_version_cached = join(self.cached_dir, '.modpack_version.txt')

    async def retry_mod(self, mod_filename, mod_downloadurl):
        with self.session.get(mod_downloadurl, stream=True) as r:
            file = io.BytesIO()
            for chunk in r.iter_content(65535):
                file.write(chunk)
            file.seek(0)
            with open(join(self.mods_cache_dir, mod_filename), 'wb') as f:
                f.write(file.getbuffer())
    
    async def save_mod(self, mod_filename, mod_downloadurl, spinner_char, mod_name):
        with Progress(
            TextColumn("[progress.description]{task.description}", table_column=Column(ratio=8)),
            TransferSpeedColumn(table_column=Column(ratio=4)),
            DownloadColumn(table_column=Column(ratio=4)),
            BarColumn(bar_width=None, table_column=Column(ratio=2)),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
            refresh_per_second=60,
            expand=True
        ) as progress:
            progress_task = progress.add_task(description=f"Downloading {mod_name}...")
            self.download_count[0] += 1
            with self.session.get(mod_downloadurl, stream=True) as r:
                file = io.BytesIO()
                try:
                    stream_length = int(r.headers['content-length'])
                except KeyError:
                    stream_length = 0
                progress.update(progress_task, total=stream_length)
                for chunk in r.iter_content(65535):
                    if not self.args.test:
                        file.write(chunk)
                    progress.update(progress_task, description=f"> {spinner_char} {mod_name}...", advance=len(chunk))
                if not self.args.test:
                    file.seek(0)
                    with open(join(self.mods_cache_dir, mod_filename), 'wb') as f:
                        f.write(file.getbuffer())
                    file.seek(0)
                    with open(join(self.mods_dir, mod_filename), 'wb') as f:
                        f.write(file.getbuffer())

    async def get_raw_data(self, url, to_json=False):
        with self.session.get(url) as r:
            if to_json:
                return r.json()
            else:
                return r.content
    
    def check_for_update(self, modpack_version):
        if exists(self.modpack_version_cached):
            self.log.info(f"{self.modpack_version_cached}")
            sys.exit()
            with open(self.modpack_version_cached, 'r') as f:
                if f.read() == modpack_version:
                    return False
                else:
                    return True
    
    async def get_github_data(self):
        github_json = await self.get_raw_data(self.repo_info['github_api'].format(self.repo_info['user'], self.repo_info['repo']), to_json=True)
        try:
            if github_json.get("message") == "Not Found":
                self.log.info(self.repo_info['github_api'].format(self.repo_info['user'], self.repo_info['repo']))
                sys.exit(self.log.critical("Release " + github_json.get("message")))
        except AttributeError:
            pass
        assets_list = {}
        for g in github_json:
            if self.args.release == g.get("name"):
                self.log.info(f"Using {g.get('name')} as the release selector.")
                modpack_version = str(g.get("id"))
                assets_list.update({"modpack_version": modpack_version})
                with open(self.modpack_version_cached, 'w') as f:
                    f.write(modpack_version)
                try:
                    assets = g.get("assets")
                except KeyError as e:
                    self.log.critical("Git data not found. Possible typo? Error: {}".format(e))
                    sys.exit(1)
                for asset in assets:
                    name = asset.get('name')
                    if name in self.repo_info['github_files']:
                        assets_list.update({asset.get('name'): await self.get_raw_data(asset.get('browser_download_url'))})
                return assets_list, modpack_version

    def create_folders(self):
        Path(self.mods_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.mods_dir}")
        Path(self.resourcepack_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.resourcepack_dir}")
        Path(self.cached_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.cached_dir}")
        Path(self.mods_cache_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.mods_cache_dir}")
        Path(join(self.cached_dir, 'cached_config')).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.cached_dir}/cached_config")

    def process_lockfile(self, lockfile, clientonly=False, serveronly=False):
        self.mods = []
        for mod in lockfile:
            if clientonly and not mod.get("serveronly"):
                self.mods.append(mod)
            elif serveronly and not mod.get("clientonly"):
                self.mods.append(mod)
            else:
                self.mods.append(mod)

    async def get_mods(self, clientonly=False, serveronly=False):
        modpack_version = ''
        if self.args.repo is not None and not '.lock' in self.args.repo:
            assets_list, modpack_version = await self.get_github_data()
            self.check_for_update(modpack_version)
            if self.args.multimc:
                ignored_cache = []
                self.log.info("Updating config...")
                config_bytes = io.BytesIO(assets_list.get('config.zip'))
                config_zip = zipfile.ZipFile(config_bytes)
                cached_config_dir = join(self.cached_dir, 'cached_config')
                config_zip.extractall(cached_config_dir)
                if exists(join(cached_config_dir, '.configignore')):
                    with open(join(cached_config_dir, '.configignore'), 'r') as f:
                        for l in f.read().splitlines():
                            ignored_cache += [l]
                self.log.info("Checking for ignored configs...")
                for c in ignored_cache:
                    if exists(join(cached_config_dir, c)):
                        self.log.info(f"Ignoring {c}...")
                        remove(join(cached_config_dir, c))
                self.log.info("Copying new config to directory...")
                shutil.copytree(cached_config_dir, self.config_dir, dirs_exist_ok=True)
                if exists(join(cached_config_dir, 'mmc-pack.json')):
                    self.log.info("Copying MultiMC JSON files...")
                    shutil.copy(join(cached_config_dir, 'mmc-pack.json'), self.current_dir)
            mods = json.loads(assets_list.get('manifest.lock'))
        else:
            if self.args.repo is not None and exists(self.args.repo):
                self.log.info(f"Using custom lockfile: {self.args.repo}")
                with open(self.args.repo, "r") as f:
                    mods = json.loads(f.read())
            else:
                if exists(join(getcwd(), 'manifest.lock')):
                    self.log.info(f"Custom lockfile not found, but we found a manifest.lock in {getcwd()}, using that instead")
                    with open(join(getcwd(), 'manifest.lock')) as f:
                        mods = json.loads(f.read())
                else:
                    sys.exit(self.log.critical(f"Custom lockfile not found: {self.args.repo}"))
        self.tasks = []
        cached_mod_ids = []
        cached_mods = []
        if exists(self.mods_cached):
            with open(self.mods_cached, 'r') as f:
                cached_mod_ids = json.loads(f.read())
        new_mods = [m.get("filename") for m in mods]
        try:
            cached_modpack_version = cached_mod_ids[-1]
        except IndexError:
            cached_modpack_version = {'mods': []}
        if self.args.multimc:
            for cm in cached_modpack_version['mods']:
                if cm not in new_mods:
                    self.log.info(f"{cm}: Flagged for update")
        for k in cached_mod_ids:
            if k['id'] == modpack_version:
                self.log.info("Already saved modpack version...")
                continue
            cached_mods.append(k)
        cached_mods.append({'id': modpack_version, 'mods': new_mods})
        if 'darwin' in platform.version().lower():
            if self.meme_activated:
                self.log.critical(f" Detected version {platform.version().lower()}! It's probably Cee...")
        self.log.info("Verifying cached mods...")
        for m in mods:
            try:
                m['resourcepack']
                self.log.info(f"Saving resourcepack {m['name']}...")
                resourcepack_r = self.session.get(f"{m['downloadUrl']}")
                print(join(self.resourcepack_dir, m['filename']))
                with open(join(self.resourcepack_dir, m['filename']), 'wb') as f:
                    f.write(resourcepack_r.content)
                continue
            except KeyError:
                pass
            filename = m.get("filename")
            if filename is None:
                self.log.warning(f"Couldn't find a download file for {m.get('slug')}... this is usually Kalka's fault")
                continue
            if clientonly and m.get("serveronly"):
                self.log.info("Skipping servermod {}".format(m.get("name")))
                continue
            if serveronly and m.get("clientonly"):
                self.log.info("Skipping clientside mod {}".format(m.get("name")))
                continue
            if 'darwin' in platform.version().lower():
                found = False
                for im in self.macos_incompatible_mods:
                    if im in filename:
                        self.log.info(f"Skipping {im}")
                        found = True
                if found:
                    continue
            self.to_copy_process.append(filename)
            download_url = m['downloadUrl']
            remote_size = m['fileLength']
            if exists(join(self.mods_cache_dir, filename)):
                # verify mods
                processed = 0
                try:
                    local_size = getsize(join(self.mods_cache_dir, filename))
                except FileNotFoundError:
                    local_size = 0
                try:
                    mod_dir_size = getsize(join(self.mods_dir, filename))
                except FileNotFoundError:
                    mod_dir_size = 0
                verified = (local_size == remote_size) and (mod_dir_size == remote_size)
                if not verified:
                    mismatch_size = (local_size != remote_size and abs(local_size - remote_size)) or (mod_dir_size != remote_size and abs(mod_dir_size - remote_size))
                    self.log.info(f"Failed to verify cached mod {filename} ({mismatch_size} byte mismatch). Retrying...")
                    self.to_process.append(filename)
                    tasks.append([filename, download_url, remote_size, m['name']])
                    continue
                self.log.debug("Using cached {} from {}".format(filename, self.mods_cache_dir))
            else:
                self.to_process.append(filename)
                tasks.append([filename, download_url, remote_size, m['name']])
        if tasks:
            from operator import itemgetter
            # Sort mods to download by filesize

            tasks = sorted(tasks, key=itemgetter(2))
            spinner = get_spinner()
            for file in reversed(tasks):
                spinner_char = next(spinner)
                filename = file[0]
                download_url = file[1]
                mod_name = file[3]
                await self.save_mod(filename, download_url, spinner_char, mod_name)
            if not self.args.test:
                self.verify_mods()
        else:
            self.log.debug("We do not have any mods to process.")
        self.session.close()
        self.log.info("Writing cached mod list to {}...".format(self.mods_cached))
        with open(self.mods_cached, 'w') as f:
            f.write(json.dumps(cached_mods))
    
    async def verify_mods(self):
        with Progress() as progress:
            total = len(self.to_process)
            verified_task = progress.add_task(description=f"Preparing to verify...", total=total)
            processed = 0
            for file in reversed(self.tasks):
                filename = file[0]
                download_url = file[1]
                try:
                    local_size = getsize(join(self.mods_cache_dir, filename))
                except FileNotFoundError:
                    local_size = 0
                try:
                    mod_dir_size = getsize(join(self.mods_dir, filename))
                except FileNotFoundError:
                    mod_dir_size = 0
                remote_size = file[2]
                verified = local_size == remote_size
                while not verified:
                    self.log.info(f"Failed to verify cached mod {filename}. Retrying...")
                    await self.retry_mod(filename, download_url)
                    local_size = getsize(join(self.mods_cache_dir, filename))
                    verified = local_size == remote_size
                verified_mod_dir = mod_dir_size == remote_size
                while not verified_mod_dir:
                    self.log.info(f"Failed to verify mod {filename} in mod directory. Retrying...")
                    await self.retry_mod(filename, download_url)
                    mod_dir_size = getsize(join(self.mods_dir, filename))
                    verified = mod_dir_size == remote_size
                processed += 1
                progress.update(verified_task, description=f"> Verified {filename}. ({processed}/{total})", advance=1)
            self.to_process.remove(file[0])


def get_spinner():
    while True:
        for cursor in "-/|\\":
            yield cursor


if __name__ == "__main__":
    w = Wolfpackmaker()
    init_traceback(console=w.log)
    w.main()
    w.create_folders()
    w.log.fancy_intro(description=f"Wolfpackmaker / {Wolfpackmaker.VERSION}")
    w.loop = asyncio.new_event_loop()
    w.loop.run_until_complete(
        w.get_mods(w.args.clientonly, w.args.serveronly)
    )
    w.log.info("We're done here.")
    w.log.save_log("wolfpackmaker")
