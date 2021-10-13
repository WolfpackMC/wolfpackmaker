import asyncio
import json
import aiohttp
import requests

from rich import inspect
from rich.logging import RichHandler
import logging

logging.basicConfig(
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
    level=logging.DEBUG
)

log = logging.getLogger("modpackmaker")

import argparse
import io
import os
import random
from simple_term_menu import TerminalMenu
from bs4 import BeautifulSoup
import sys
import time
import zipfile

from lock import process_modpack_config

game_version = ['1.12.2']

curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/'
modpack_search_url = f'{curseforge_url}search?gameId=432&categoryId=4472&searchFilter='

def parse_args(parser):
    args = parser.parse_args()
    return args


def init_args():
    parser = argparse.ArgumentParser(
        description='Wolfpackmaker (modpackmaker.py) (https://woofmc.xyz)'
    )
    parser.add_argument('modpack', metavar='MODPACK_SLUG', type=str, help='Search indication for a CurseForge modpack.')
    return parser

parser = init_args()
args = parse_args(parser)

headers = {
    'User-Agent': 'Wolfpackmaker (https://woofmc.xyz)',
    'Accept-Encoding': None
}

async def resolve_mod(session, file):
    async with session.get(f"{curseforge_url}{file['projectID']}") as r:
        data_mod = await r.json()
    async with session.get(f"{curseforge_url}{file['projectID']}/file/{file['fileID']}") as r:
        data_file = await r.json()
    mod_yaml = f"- {data_mod['slug']}:\n"
    mod_yaml += f"    url: {data_file['downloadUrl']}\n"
    log.info(f"{data_mod['slug']}...")
    return mod_yaml

async def resolve_mods(session, files):
    tasks = []
    async_session = aiohttp.ClientSession()
    for file in files:
        task = asyncio.create_task(resolve_mod(async_session, file))
        tasks.append(task)
    future = await asyncio.gather(*tasks)
    await async_session.close()
    return ''.join(future)

def main():
    session = requests.Session()
    session.headers.update(headers)
    try:
        int(args.modpack)
        r = session.get(f"{curseforge_url}{args.modpack}")
        result = [json.loads(r.content)]
        if len(result) == 1:
            selection = result[0]
        else:
            sys.exit(log.error("No modpack found."))
    except ValueError:
        r = session.get(f"{modpack_search_url}{args.modpack}")
        r.status_code != 200 and sys.exit(log.critical(f"Code {r.status_code}: {r.content}"))
        result = json.loads(r.content)
        if len(result) > 1:
            log.info("Multiple modpack choices found. Select the modpack of choice below.")
            terminal_menu = TerminalMenu([m['name'] for m in result])
            menu_entry_index = terminal_menu.show()
            selection = result[menu_entry_index]
        elif len(result) == 1:
            selection = result[0]
        else:
            sys.exit(log.error(f"No modpack found using search query {args.modpack}."))
    files = [f for f in selection['latestFiles']]
    if len(files) > 1:
        log.info(f"Multiple files for {selection['name']}. Choose which one you would like.")
        terminal_menu = TerminalMenu([f['displayName'] + ' (released on ' + f['fileDate'] + ')' for f in files])
        menu_entry_index = terminal_menu.show()
        file_selection = files[menu_entry_index]
    elif len(files) == 1:
        file_selection = files[0]
    else:
        sys.exit(log.error("No file found... somehow?"))
    zip_dir = f"modpack_data/{selection['slug']}"
    if not os.path.exists(zip_dir):
        modpack_file = io.BytesIO()
        with requests.get(file_selection['downloadUrl'], stream=True) as r:
            print(f"Downloading {file_selection['downloadUrl']}... ({r.headers['content-length']} bytes)")
            for chunk in r.iter_content(65535):
                modpack_file.write(chunk)
        zip = zipfile.ZipFile(modpack_file)
        zip.extractall(zip_dir)
        zip.close()
        modpack_file.close()
    manifest_yaml = str()
    with open(f"{zip_dir}/manifest.json") as f:
        cf_modpack_manifest = json.loads(f.read())
    inspect(cf_modpack_manifest)
    if os.path.exists(f"{zip_dir}/manifest.yml"):
        with open(f"{zip_dir}/manifest.yml") as f:
            manifest_yaml = f.read()
    else:
        if 'forge' in cf_modpack_manifest['minecraft']['modLoaders'][0]['id']:
            manifest_yaml += 'modloader: Forge\n'
        elif 'fabric' in cf_modpack_manifest['minecraft']['modLoaders'][0]['id']:
            manifest_yaml += 'modloader: Fabric\n'
        manifest_yaml += f'version: {cf_modpack_manifest["minecraft"]["version"]}\n'
        manifest_yaml += f'mods:\n'
        log.info("Resolving mods...")
        mods_yaml = asyncio.run(resolve_mods(session, cf_modpack_manifest['files']))
        manifest_yaml += mods_yaml
    if '- optifine:' in manifest_yaml.splitlines():
        do_optifine = False
    else:
        do_optifine = input("> Add OptiFine? (y/n) ").lower() == 'y'
    if do_optifine:
        optifine_url = "https://get.kalka.io/Optifine"
        log.info("Looking for OptiFine...")
        optifine_r = session.get(optifine_url)
        optifine_html = BeautifulSoup(optifine_r.content)
        for href in optifine_html.find_all('a'):
            optifine_link = href.get('href')
            if file_selection['gameVersion'][0] in optifine_link:
                break
        manifest_yaml += '- optifine:\n'
        manifest_yaml += f'    url: {optifine_url}{optifine_link}'
    log.info("Saving manifest.yml...")
    log.info(manifest_yaml)
    with open(f"{zip_dir}/manifest.yml", "w") as f:
        f.write(manifest_yaml)
    log.info("Locking mods...")
    modpack_lock = asyncio.run(process_modpack_config(manifest=manifest_yaml))
    with open(f"{zip_dir}/manifest.lock", "w") as f:
        f.write(json.dumps(modpack_lock))
    log.info("Done.")


main()
