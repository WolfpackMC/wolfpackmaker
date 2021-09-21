#!/usr/bin/env python3

import aiohttp
import argparse
import asyncio
import io
import json
import logging
import owoify
import distutils
import platform
import shutil
import sys
import time
import zipfile


from distutils.dir_util import copy_tree
from os.path import dirname, abspath, exists, join
from os import remove, getcwd, listdir
from pathlib import Path
from pyfiglet import Figlet
from rich.traceback import install as init_traceback
from rich.logging import RichHandler
from rich.progress import Progress

log = logging.getLogger("rich")

class Wolfpackmaker:
    VERSION = f'0.2.0'

headers = {
    'User-Agent': 'Wolfpackmaker (https://woofmc.xyz)'
}

macos_incompatible_mods = [
    "itlt"
]

meme_activated = True


def parse_args(parser):
    args = parser.parse_args()
    return args


def init_args():
    parser = argparse.ArgumentParser(
        description='Wolfpackmaker (https://woofmc.xyz)'
    )
    parser.add_argument('-v', '--verbose', help='Increase output verbosity.', action='store_true')
    parser.add_argument('-r', '--repo', help='Wolfpack modpack repository from https://git.kalka.io e.g'
                                             '--repo Odin, from https://git.kalka.io/Wolfpack/Odin')
    parser.add_argument('-mmc', '--multimc', help='Enable MultiMC setup.', action='store_true')
    parser.add_argument('-d', '--download', help='Custom download directory')
    parser.add_argument('--cache', help='Custom cache directory')
    parser.add_argument('-c', '--clientonly', help='Enable clientonly.', action='store_true', default=False)
    parser.add_argument('-s', '--serveronly', help='Enable serveronly.', action='store_true', default=False)
    parser.add_argument('-rs', '--release', help='Get release name.', default='latest')
    parser.add_argument('--singlethread', help='Run on one thread only.', action='store_true')
    return parser


parser = init_args()
args = parse_args(parser)

user = "WolfpackMC"
repo = args.repo
github_api = "https://api.github.com/repos/{}/{}/releases"
github_files = ['manifest.lock', 'config.zip']

parent_dir = dirname(dirname(abspath(__file__)))
current_dir = dirname(abspath(__file__))
if args.download:
    mods_dir = join(current_dir, args.download)
else:
    mods_dir = join(parent_dir, '.minecraft/mods')
if args.cache:
    mods_cache_dir = join(current_dir, args.cache)
else:
    mods_cache_dir = join(dirname(parent_dir), '.mods_cached')
config_dir = join(parent_dir, '.minecraft/config')
cached_dir = join(parent_dir, '.wolfpackmaker')
mods_cached = join(cached_dir, '.cached_mods.json')
modpack_version_cached = join(cached_dir, '.modpack_version.txt')


def fancy_intro():
    f = Figlet()
    log.info(str('').join(['####' for _ in range(16)]))
    log.info(f.renderText(("woofmc.xyz")))
    import random
    keywords = random.choice(
        ['A custom made Minecraft modpack script. Nothing special, hehe.',
         'Please don\'t tell anyone about this...',
         'Hehe. UwU, It\'s all we have, I know. I\'m sorry!'
         ]
    )
    log.info(owoify.owoify(keywords))
    log.info(str('').join(['####' for _ in range(16)]))


async def save_mod(mod_filename, mod_downloadurl, session):
    async with session.get(mod_downloadurl) as r:
        with open(join(mods_cache_dir, mod_filename), 'wb') as f:
            async for data in r.content.iter_chunked(65535):
                f.write(data)
    return mod_filename


def save_mod_sync(mod_filename, mod_downloadurl):
    import urllib3
    session = urllib3.PoolManager(headers=headers)
    r = session.request("GET", mod_downloadurl, preload_content=False)
    with open(join(mods_cache_dir, mod_filename), 'wb') as f:
        for data in r.stream(65535):
            f.write(data)

async def get_raw_data(session, url, to_json=False):
    async with session.get(url) as r:
        if to_json:
            return await r.json()
        else:
            return await r.read()

to_process = []  # mods to process
to_copy_process = [] # mods to copy


def check_for_update(modpack_version):
    if exists(modpack_version_cached):
        with open(modpack_version_cached, 'r') as f:
            if f.read() == modpack_version:
                return False
            else:
                return True


async def get_github_data(session):
    github_json = await get_raw_data(session, github_api.format(user, repo), to_json=True)
    try:
        if github_json.get("message") == "Not Found":
            log.info(github_api.format(user, repo))
            sys.exit(log.critical("Release " + github_json.get("message")))
    except AttributeError:
        pass
    assets_list = {}
    for g in github_json:
        if args.release == g.get("name"):
            log.info(f"Using {g.get('name')} as the release selector.")
            modpack_version = str(g.get("id"))
            assets_list.update({"modpack_version": modpack_version})
            with open(modpack_version_cached, 'w') as f:
                f.write(modpack_version)
            try:
                assets = g.get("assets")
            except KeyError as e:
                log.critical("Git data not found. Possible typo? Error: {}".format(e))
                sys.exit(1)
            for asset in assets:
                name = asset.get('name')
                if name in github_files:
                    assets_list.update({asset.get('name'): await get_raw_data(session, asset.get('browser_download_url'))})
            return assets_list, modpack_version


def process_lockfile(lockfile, clientonly=False, serveronly=False):
    mods = []
    for mod in lockfile:
        if clientonly and not mod.get("serveronly"):
            mods.append(mod)
        elif serveronly and not mod.get("clientonly"):
            mods.append(mod)
        else:
            mods.append(mod)
    return mods


def create_folders():
    Path(mods_dir).mkdir(parents=True, exist_ok=True)
    Path(cached_dir).mkdir(parents=True, exist_ok=True)
    Path(mods_cache_dir).mkdir(parents=True, exist_ok=True)
    Path(join(cached_dir, 'cached_config')).mkdir(parents=True, exist_ok=True)


async def get_mods(clientonly=False, serveronly=False):
    session = aiohttp.ClientSession(headers=headers)
    modpack_version = ''
    if args.repo is not None and not '.lock' in args.repo:
        assets_list, modpack_version = await get_github_data(session)
        if args.multimc:
            ignored_cache = []
            log.info("Cleaning mods folder...")
            start_time = time.time()
            for f in listdir(mods_dir):  #temporary
                try:
                    remove(join(mods_dir, f))
                except PermissionError:
                    pass
                except IsADirectoryError:
                    pass
            log.info(f"Finished in {time.time() - start_time}s.")
            log.info("Updating config...")
            config_bytes = io.BytesIO(assets_list.get('config.zip'))
            config_zip = zipfile.ZipFile(config_bytes)
            cached_config_dir = join(cached_dir, 'cached_config')
            config_zip.extractall(cached_config_dir)
            if exists(join(cached_config_dir, '.configignore')):
                with open(join(cached_config_dir, '.configignore'), 'r') as f:
                    for l in f.readlines():
                        ignored_cache += [l]
            log.info("Checking for ignored configs...")
            for c in ignored_cache:
                if exists(join(cached_config_dir, c)):
                    log.info(f"Ignoring {c}...")
                    remove(join(cached_config_dir, c))
            log.info("Moving new config to directory...")
            copy_tree(cached_config_dir, config_dir)
            if exists(join(cached_config_dir, 'mmc-pack.json')):
                log.info("Copying MultiMC JSON files...")
                shutil.copy(join(cached_config_dir, 'mmc-pack.json'), parent_dir)
        mods = json.loads(assets_list.get('manifest.lock'))
    else:
        if args.repo is not None and exists(args.repo):
            log.info(f"Using custom lockfile: {args.repo}")
            with open(args.repo, "r") as f:
                mods = json.loads(f.read())
        else:
            if exists(join(getcwd(), 'manifest.lock')):
                log.info(f"Custom lockfile not found, but we found a manifest.lock in {getcwd()}, using that instead")
                with open(join(getcwd(), 'manifest.lock')) as f:
                    mods = json.loads(f.read())
            else:
                sys.exit(log.critical(f"Custom lockfile not found: {args.repo}"))
    tasks = []
    cached_mod_ids = []
    cached_mods = []
    if exists(mods_cached):
        with open(mods_cached, 'r') as f:
            cached_mod_ids = json.loads(f.read())
    new_mods = [m.get("filename") for m in mods]
    cached_modpack_version = str()
    if args.multimc:
        for cm in cached_mod_ids:
            try:
                cached_modpack_version = cm.get("id")
                if cached_modpack_version == modpack_version:
                    for f in cm.get("mods"):
                        if f not in new_mods:
                            log.info("Flagging {} for update...".format(f))
                            filedir = join(mods_dir, f)
                            if exists(filedir):
                                remove(filedir)
                            else:
                                log.warning(f"{filedir} does not exist... why?")
                    continue
                cached_mods.append(cm)
            except AttributeError:
                cached_modpack_version = 'none'
    if modpack_version != cached_modpack_version:
        log.info(f"Saving modpack version {modpack_version}...")
    cached_mods.append({'id': modpack_version, 'mods': new_mods})
    log.info(f"Detected version {platform.version()}")
    for m in mods:
        filename = m.get("filename")
        if filename is None:
            log.warning(f"Couldn't find a download file for {m.get('slug')}... this is usually Kalka's fault")
            continue
        if clientonly and m.get("serveronly"):
            log.info("Skipping servermod {}".format(m.get("name")))
            continue
        if serveronly and m.get("clientonly"):
            log.info("Skipping clientside mod {}".format(m.get("name")))
            continue
        if 'darwin' in platform.version().lower():
            if meme_activated:
                log.critical(f" Detected version {platform.version.lower()}! It's probably Cee...")
            found = False
            for im in macos_incompatible_mods:
                if im in filename:
                    log.info(f"Skipping {im}")
                    found = True
            if found:
                continue
        to_copy_process.append(filename)
        if not exists(join(mods_dir, filename)) or not exists(
                join(mods_cache_dir, filename)):  # if it does not exist in the folder
            if exists(join(mods_cache_dir, filename)):
                log.debug("Using cached {} from {}".format(filename, mods_cache_dir))
            else:
                to_process.append(filename)
                download_url = m.get("downloadUrl")
                if not args.singlethread:
                    task = asyncio.ensure_future(save_mod(filename, download_url, session))
                    tasks.append(task)
                else:
                    save_mod_sync(filename, download_url)
                    log.info(f"Downloaded {download_url}.")
                    to_process.remove(filename)
    if tasks:
        with Progress() as progress:
            total = len(to_process)
            download_task = progress.add_task(description=f"Preparing to download...", total=total)
            processed = 0
            for coro in asyncio.as_completed(tasks):
                filename = await coro
                processed += 1
                to_process.remove(filename)
                progress.update(download_task, description=f"Downloaded {filename}. ({processed}/{total})", advance=1)
    else:
        log.debug("We do not have any mods to process.")
    await session.close()
    processed = 0
    with Progress() as progress:
        total = len(to_copy_process)
        copy_task = progress.add_task(description=f"Copying mods... ({processed}/{total}", total=total)
        for m in to_copy_process:
            if exists(join(mods_cache_dir, m)):
                shutil.copy(join(mods_cache_dir, m), join(mods_dir, m))
                processed += 1
                progress.update(copy_task, description=f"Copied {m}. ({processed}/{total})", advance=1)
    log.info("Writing cached mod list to {}...".format(mods_cached))
    with open(mods_cached, 'w') as f:
        f.write(json.dumps(cached_mods))


def assemble_logger(verbosity):
    debug_mode = logging.DEBUG if verbosity else logging.INFO
    logging.basicConfig(
        level=(debug_mode),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()]
    )
    current_time = time.time()
    logfile_name = f'wolfpackmaker-{current_time}-output.log'
    logfile = join(cached_dir, logfile_name)
    fh = logging.FileHandler(logfile)
    fh.setLevel(debug_mode)
    log.addHandler(fh)


def main():
    init_traceback()
    create_folders()
    assemble_logger(args.verbose)
    fancy_intro()
    log.info(f"Wolfpackmaker / {Wolfpackmaker.VERSION}")
    loop = asyncio.get_event_loop()
    # TODO: Server support, this is the Oil Ocean Zone of Wolfpackmaker :^)
    try:
        loop.run_until_complete(
            get_mods(clientonly=args.clientonly, serveronly=args.serveronly))  # The todo is for this purpose
    except KeyboardInterrupt or InterruptedError:
        for mod in to_process:
            if exists(join(mods_dir, mod)):
                log.debug("Cleaning {} as it was in the middle of being downloaded".format(mod))
                try:
                    remove(join(mods_dir, mod))
                except FileNotFoundError:
                    log.warning("{} not found, skipping anyway".format(mod))
    log.info("We're done here.")


main()
