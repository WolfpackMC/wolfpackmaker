#!/usr/bin/env python3

import aiohttp
import argparse
import asyncio
import io
import json
import logging
import owoify
import sys
import time
import zipfile


from os.path import dirname, abspath, exists, join
from os import remove, getcwd
from pathlib import Path
from pyfiglet import Figlet
from rich.traceback import install as init_traceback
from rich.logging import RichHandler
from rich.progress import Progress

log = logging.getLogger("rich")

headers = {
    'User-Agent': 'Wolfpackmaker (https://woofmc.xyz)'
}


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
    parser.add_argument('-rs', '--rselector', help='GitHub Releases index for branched releases.', default=0)
    return parser


parser = init_args()
args = parse_args(parser)

user = "kalkafox"
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
         'Please don\'t tell anyone about this...'
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


async def get_raw_data(session, url, to_json=False):
    async with session.get(url) as r:
        if to_json:
            return await r.json()
        else:
            return await r.read()

to_process = []  # mods to process


def check_for_update(modpack_version):
    if exists(modpack_version_cached):
        with open(modpack_version_cached, 'r') as f:
            if f.read() == modpack_version:
                return False
            else:
                return True


async def get_github_data(session):
    github_json = await get_raw_data(session, github_api.format(user, repo), to_json=True)
    assets_list = {}
    modpack_version = str(github_json[int(args.rselector)].get("id"))
    assets_list.update({"modpack_version": modpack_version})
    with open(modpack_version_cached, 'w') as f:
        f.write(modpack_version)
    try:
        assets = github_json[int(args.rselector)].get("assets")
    except KeyError as e:
        log.critical("Git data not found. Possible typo? Error: {}".format(e))
        sys.exit(1)
    for asset in assets:
        name = asset.get('name')
        if name in github_files:
            assets_list.update({asset.get('name'): await get_raw_data(session, asset.get('browser_download_url'))})
    return assets_list


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


async def get_mods(clientonly=False, serveronly=False):
    Path(mods_dir).mkdir(parents=True, exist_ok=True)
    Path(cached_dir).mkdir(parents=True, exist_ok=True)
    Path(mods_cache_dir).mkdir(parents=True, exist_ok=True)
    session = aiohttp.ClientSession(headers=headers)
    if args.repo is not None and not '.lock' in args.repo:
        assets_list = await get_github_data(session)
        if args.multimc:
            if check_for_update(assets_list.get("modpack_version")):
                log.info("Updating config...")
                config_bytes = io.BytesIO(assets_list.get('config.zip'))
                config_zip = zipfile.ZipFile(config_bytes)
                config_zip.extractall(parent_dir)
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
    import shutil
    for m in mods:
        filename = m.get("filename")
        if clientonly and m.get("serveronly"):
            log.info("Skipping servermod {}".format(m.get("name")))
            continue
        if serveronly and m.get("clientonly"):
            log.info("Skipping clientside mod {}".format(m.get("name")))
            continue
        if filename not in cached_mod_ids:
            log.info("Flagging {} for update...".format(filename))
            try:
                remove(join(mods_dir, filename))
            except FileNotFoundError:
                log.warning("{} not found, skipping anyway".format(filename))
        if not exists(join(mods_dir, filename)) or not exists(
                join(mods_cache_dir, filename)):  # if it does not exist in the folder
            if exists(join(mods_cache_dir, filename)):
                log.debug("Using cached {} from {}".format(filename, mods_cache_dir))
                shutil.copy(join(mods_cache_dir, filename), join(mods_dir, filename))
            else:
                download_url = m.get("downloadUrl")
                task = asyncio.ensure_future(save_mod(filename, download_url, session))
                to_process.append(filename)
                tasks.append(task)
    if tasks:
        with Progress() as progress:
            download_task = progress.add_task(description="Preparing to download...", total=len(to_process))
            for coro in asyncio.as_completed(tasks):
                filename = await coro
                to_process.remove(filename)
                progress.update(download_task, description=f"Downloading {filename}...", advance=1)
                shutil.copy(join(mods_cache_dir, filename), join(mods_dir, filename))
    else:
        log.debug("We do not have any mods to process.")
    await session.close()
    log.info("Writing cached mod list to {}...".format(mods_cached))
    for m in mods:
        if clientonly and m.get("serveronly"):
            continue
        if serveronly and m.get("clientonly"):
            continue
        cached_mods.append(m.get("filename"))
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
    logfile = join(cached_dir, f'wolfpackmaker-{time.time()}-output.log')
    fh = logging.FileHandler(logfile)
    fh.setLevel(debug_mode)
    log.addHandler(fh)


def main():
    init_traceback()
    assemble_logger(args.verbose)
    fancy_intro()
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
