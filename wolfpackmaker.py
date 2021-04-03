import aiohttp
import argparse
import asyncio
import io
import json
import logging
import owoify
import sys
import zipfile


from os.path import dirname, abspath, exists, join
from os import remove
from pathlib import Path
from pyfiglet import Figlet
from rich.logging import RichHandler
from rich.progress import Progress

log = logging.getLogger("rich")

parent_dir = dirname(dirname(abspath(__file__)))
mods_dir = join(parent_dir, '.minecraft/mods')
mods_cache_dir = join(dirname(parent_dir), '.mods_cached')
config_dir = join(parent_dir, '.minecraft/config')
cached_dir = join(parent_dir, '.wolfpackmaker')
mods_cached = join(cached_dir, '.cached_mods.json')
modpack_version_cached = join(cached_dir, '.modpack_version.txt')

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
                                             '--repo Odin, from https://git.kalka.io/Wolfpack/Odin', required=True)
    return parser


parser = init_args()
args = parse_args(parser)

user = "Wolfpack"
repo = args.repo
gitea_api = "https://git.kalka.io/api/v1/repos/{}/{}/releases"
gitea_files = ['manifest.lock', 'config.zip']


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
        return await r.read(), mod_filename


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
                return True
            else:
                return False


async def get_gitea_data(session):
    gitea_json = await get_raw_data(session, gitea_api.format(user, repo), to_json=True)
    assets_list = {}
    modpack_version = gitea_json[0].get("name")
    assets_list.update({"modpack_version": modpack_version})
    with open(modpack_version_cached, 'w') as f:
        f.write(modpack_version)
    try:
        assets = gitea_json[0].get("assets")
    except KeyError as e:
        log.critical("Git data not found. Possible typo? Error: {}".format(e))
        sys.exit(1)
    for asset in assets:
        name = asset.get('name')
        if name in gitea_files:
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
    session = aiohttp.ClientSession(headers=headers)
    assets_list = await get_gitea_data(session)
    tasks = []
    if check_for_update(assets_list.get("modpack_version")):
        log.debug("Updating config...")
        config_bytes = io.BytesIO(assets_list.get('config.zip'))
        config_zip = zipfile.ZipFile(config_bytes)
        config_zip.extractall(parent_dir)
    cached_mod_ids = []
    if exists(mods_cached):
        with open(mods_cached, 'r') as f:
            cached_mod_ids = json.loads(f.read())
    mods = json.loads(assets_list.get('manifest.lock'))
    import shutil
    for m in mods:
        if clientonly and m.get("serveronly"):
            continue
        if serveronly and m.get("clientonly"):
            continue
        filename = m.get("filename")
        if filename not in cached_mod_ids:
            if exists(join(mods_dir, filename)):
                log.debug("Flagging {} for update...".format(filename))
                try:
                    remove(join(mods_dir, filename))
                except FileNotFoundError:
                    log.debug("{} not found, skipping anyway".format(filename))
        if not exists(join(mods_dir, filename)) or not exists(join(mods_cache_dir, filename)):  # if it does not exist in the folder
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
            keywords = [
                'Reticulating splines... >w>',
                'Installing rockets... owo',
                'Ensuring integrity... xD',
                'Adding more cringe... x3',
                'Installing cringe... >w<',
                'Making sure we have the right assets... ^.^'
            ]
            download_progress = progress.add_task("Downloading {} mods...".format(len(tasks)), total=len(tasks))
            Path(mods_cache_dir).mkdir(parents=True, exist_ok=True)
            for coro in asyncio.as_completed(tasks):
                import random
                random_message = owoify.owoify(random.choice(keywords))
                completed = (-len(to_process) + len(tasks)) + 1
                progress.update(download_progress,
                                description="Downloading: {}... {}/{} - ({})".format(filename,
                                                                                     completed,
                                                                                     len(tasks), random_message))
                data, filename = await coro
                mod_file = io.BytesIO(data)
                with open(join(mods_cache_dir, filename), 'wb') as f:
                    progress.update(download_progress,
                                    advance=1,
                                    description="Saving: {}... {}/{} - ({})".format(filename,
                                                                                    completed,
                                                                                    len(tasks), random_message))
                    f.write(mod_file.read())
                    to_process.remove(filename)
                shutil.copy(join(mods_cache_dir, filename), join(mods_dir, filename))
    else:
        log.debug("We do not have any mods to process.")
    await session.close()
    log.info("Writing cached mod list to {}...".format(mods_cached))
    with open(mods_cached, 'w') as f:
        f.write(json.dumps([mod.get('fileName') for mod in mods]))


def assemble_logger(verbosity):
    logging.basicConfig(
        level=(logging.DEBUG if verbosity else logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()]
    )


def main():
    assemble_logger(args.verbose)
    fancy_intro()
    loop = asyncio.get_event_loop()
    # TODO: Server support, this is the Oil Ocean Zone of Wolfpackmaker :^)
    try:
        loop.run_until_complete(get_mods(clientonly=True))  # The todo is for this purpose
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
