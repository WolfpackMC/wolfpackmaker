import io
import aiohttp
import argparse
import asyncio
import datetime
import json
import logging
import sys
import time
import yaml


from aiohttp.client_exceptions import ContentTypeError
from collections import Counter
from os.path import basename
from rich.logging import RichHandler
from rich.traceback import install as init_traceback

from fancy_intro import fancy_intro

TYPE_FABRIC = 4
TYPE_FORGE = 1

# noinspection PyArgumentList
logging.basicConfig(
    level=logging.DEBUG, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("rich")

found_mods = []


def parse_args(parser):
    args = parser.parse_args()
    return args


def init_args():
    parser = argparse.ArgumentParser(
        description='Wolfpackmaker (lock.py) (https://woofmc.xyz)'
    )
    parser.add_argument('-v', '--verbose', help='Increase output verbosity.', action='store_true')
    parser.add_argument('-m', '--manifest', help='Optional location for the manifest e.g /opt/manifests/manifest.yml.'
                                                 '\nDefaults to workdir (manifest.yml)')
    parser.add_argument('-nomod', '--nomodleftbehind', help='Enacts the No Mod Left Behind Act. Finds all missing mods'
                                                            '\nusing CurseForge API if said mod is not found in the CurseForge DB.'
                                                            '\nDefaults to true', default=True)
    return parser


parser = init_args()
args = parse_args(parser)

async def fetch_file(curseforge_url, mod, session, fileId):
    files_url = curseforge_url + '{}/file/{}'.format(mod.get("id"), fileId)
    async with session.get(files_url) as r:
        try:
            file = await r.json()
        except ContentTypeError:
            log.error(mod)
            sys.exit(log.error("ContentType error."))
    return file


async def fetch_mod(curseforge_url, mod_id, session):
    mod_url = curseforge_url + str(mod_id)
    async with session.get(mod_url) as r:
        # log.debug("Responding to request {}...".format(mod_url))
        try:
            mod = await r.json()
        except ContentTypeError:
            sys.exit(log.error("ContentType error."))
    return mod


async def search_mod(curseforge_url, mod_slug, session):
    search_url = curseforge_url + 'search?gameId=432&sectionId=6&searchfilter={}'.format(mod_slug)
    async with session.get(search_url) as r:
        mods = await r.json()
    for m in mods:
        if m.get("slug") == mod_slug:
            log.info("Found {} as {} via CurseForge API! [{}] [{}]".format(mod_slug, m.get("slug"), m.get("name"),
                                                                           m.get("id")))
            return m
    log.warning(f"We still cannot find {mod_slug} in the API... wtf?")


modloader = ''

import datetime


async def get_mod_file(curseforge_url, modpack_manifest, version, mc_version, mod, session, is_file_found):
    if is_file_found:
        return
    mod_compat = version.get("modLoader")
    if modpack_manifest.get("modloader").lower() == 'forge' and mod_compat == TYPE_FABRIC:
        return
    if modpack_manifest.get("modloader").lower() == 'fabric' and mod_compat == TYPE_FORGE:
        return
    if version.get("gameVersion") in mc_version:
        file_id = version.get("projectFileId")
        file = await fetch_file(curseforge_url, mod, session, file_id)
        return file


async def fetch_mod_data(curseforge_url, mod, session, modpack_manifest, cf_data, completed, to_complete):
    start_time = time.time()
    mc_version = [modpack_manifest.get("version")]
    if "1.16.5" in mc_version:
        for i in range(1, 5):
            mc_version.append(f"1.16.{i}")
    file_found = False

    try:
        latest_files = mod['latest_files']
    except KeyError:
        latest_files = mod['gameVersionLatestFiles']
    
    for version in latest_files:
            file = asyncio.create_task(get_mod_file(curseforge_url, modpack_manifest, version, mc_version, mod, session, file_found))
            await file
            file = file.result()
            if not file: continue
            file_found = True
            deps = []
            for dep in file.get("dependencies"):
                if dep.get("addonId") in [m.get("id") for m in found_mods]:
                    continue
                deps += [d for d in cf_data if dep.get("addonId") == d.get("id") and dep.get("type") == 3]
            dep_file_found = False
            for d in deps:
                log.info(f"Resolving dependency {d.get('name')} for mod {mod.get('name')}...")
                for df in d.get("latest_files"):
                    dep_file = await get_mod_file(curseforge_url, modpack_manifest, df, mc_version, d, session, dep_file_found)
                    if not dep_file: continue
                    dep_file_found = True
                    if d.get("id") in [m.get("id") for m in found_mods]:
                        continue
                    found_mods.append({
                        "id": d.get("id"),
                        "slug": d.get("slug"),
                        "name": d.get("name"),
                        "downloadUrl": dep_file.get("downloadUrl"),
                        "filename": dep_file.get("fileName")
                    })
            for m in found_mods:
                if m.get('downloadUrl') is not None:
                    continue
                if m.get("id") == mod.get("id"):
                    m.update({'downloadUrl': file.get('downloadUrl'), 'filename': file.get('fileName')})
    completed[0] += 1
    log.info(f"[LOCK] [{completed[0]}/{to_complete[0]}] {mod.get('name')} took {time.time() - start_time:.3f} seconds.")
    if not file_found:
        log.warning(
            f"Mod {mod.get('slug')} [{mod.get('name')}] does not have an apparent version for {mc_version}, tread with caution")


async def process_modpack_config():
    chunked = True  # Should chunk
    curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/'
    try:
        open(args.manifest)
    except TypeError:
        pass
    except FileNotFoundError:
        log.critical('{} was not found. Make sure the directory is correct.'.format(args.manifest))
        log.info("Defaulting to manifest.yml. Waiting 3 seconds...")
        await asyncio.sleep(3)
        args.manifest = 'manifest.yml'
    with open(args.manifest or 'manifest.yml', 'r') as f:
        modpack_manifest = yaml.load(f.read(), Loader=yaml.SafeLoader)
    mods = modpack_manifest.get("mods")
    # check for duplicates
    duplicate_mods = []
    for idx, mod in enumerate(mods):
        for k, v in mods[idx].items():
            duplicate_mods.append(k)
    if [k for k,v in Counter(duplicate_mods).items() if v>1]:
        sys.exit(log.error(f"Found duplicates in the manifest file. Please remove them before continuing:\n> {[k for k,v in Counter(duplicate_mods).items() if v>1]}"))
    curseforge_download_url = "https://get.kalka.io/curseforge.json"
    session = aiohttp.ClientSession()
    log.debug(f"Established session {session}")
    log.info(f"Reading CurseForge data from {curseforge_download_url}")
    start_time = time.time()
    async with session.get(curseforge_download_url) as r:
        date = datetime.datetime.strptime(r.headers.get("last-modified"), "%a, %d %b %Y %H:%M:%S %Z")
        log.info(f"CurseForge DB date is {datetime.datetime.strftime(date, '%B %d, %Y at %H:%M:%Sz')}")
        if chunked:
            log.info("Reading chunked data... (it's probably big)")
            data = io.BytesIO()
            async for c in r.content.iter_chunked(65535):
                data.write(c)
            data.seek(0)
            curseforge_data = json.loads(data.read())
        else:
            data = await r.read()
            curseforge_data = json.loads(data)
    log.info(f"Took {time.time() - start_time:.2f}s. {len(curseforge_data)} mods recognized.")
    tasks = []
    to_complete = [0]
    completed = [0]
    for idx, mod in enumerate(mods):
        for k, v in mods[idx].items():
            client_only, server_only, optional = False, False, False
            match v:
                case {'clientonly': True}:
                    client_only = True
                case {'serveronly': True}:
                    server_only = True
                case {'optional': True}:
                    optional = True
            not_found_msg = f'This happened because we exhausted all efforts to search for {k}, and the only info we know about it is the mod slug, which is just {k}. The easiest fix to this is to visit https://www.curseforge.com/minecraft/mc-mods/{k} and copy the value of "Project ID", and append it to the corresponding mod in the yaml manifest, e.g:\n- {k}:\n    id: <id>... \nThe script will continue and disregard this specific mod, but it will be considered a mod we cannot digest!'
            finished_suffix = " (took {:.2f} seconds)"
            start_time
            try:
                mod_data = [m for m in curseforge_data if k == m['slug']][0]
            except IndexError:
                mod_data = [{
                    "id": None,
                    "name": k
                }][0]
            custom = []
            match v:
                case {'url': url}:
                    found_mods.append({
                        "id": mod_data['id'] or None,
                        "name": mod_data['name'] or k,
                        "slug": k,
                        # the = is for optifine
                        "filename": '=' in url and url.split("=")[1] or basename(url),
                        "downloadUrl": url,
                        "clientonly": client_only,
                        "serveronly": server_only,
                        "optional": optional,
                        "custom": True
                    })
                    to_complete[0] += 1
                    completed[0] += 1
                    log.info(f"[LOCK] [{completed[0]}/{to_complete[0]}] Resolved {mod_data['name']}, using custom URL {url}")
                    custom.append(True)
            if custom: continue
            if mod_data:
                log.info(f"[MATCH] [{completed[0]}/{to_complete[0]}] Resolved {mod_data['name']} {finished_suffix.format(time.time() - start_time)}!")
                found_mods.append({
                    "id": mod_data['id'] or None,
                    "name": mod_data['name'] or k,
                    "slug": k,
                    "clientonly": client_only,
                    "serveronly": server_only,
                    "optional": optional
                })
                task = asyncio.create_task(fetch_mod_data(curseforge_url, mod_data, session, modpack_manifest, curseforge_data, completed, to_complete))
                tasks.append(task)
                to_complete[0] += 1
            else:
                match v:
                    case {'id': id}:
                            log.info(f"Using {id} for {k}. This should guarantee a positive match.")
                            cf_get = await session.get(curseforge_url + str(id))
                            data = await cf_get.json()
                            if k != data['slug']:
                                sys.exit(log.critical(f"Mod mismatch! {k} =/= {data['slug']}. This is usually impossible unless you are using the wrong mod ID."))
                            log.info(f"[MATCH] [{completed[0]}/{to_complete[0]}] Resolved {data['name']} through CurseForge!")
                            found_mods.append({
                                "id": data['id'],
                                "slug": data['slug'],
                                "name": data['name'],
                                "clientonly": client_only,
                                "serveronly": server_only,
                                "optional": optional
                            })
                            task = asyncio.create_task(fetch_mod_data(curseforge_url, data, session, modpack_manifest, curseforge_data, completed, to_complete))
                            tasks.append(task)
                            to_complete[0] += 1
                    case None:
                        log.info(f"{k} was not found. {not_found_msg}")
                        continue
            if not mod_data:
                continue

    await asyncio.gather(*tasks)
    await session.close()


def save_lockfile():
    log.info("Saving lockfile...")
    with open('manifest.lock', 'w') as f:
        f.write(json.dumps(found_mods))
    log.info("Saving pretty-printed file...")
    with open('manifest.json', 'w') as f:
        f.write(json.dumps(found_mods, indent=2))


def main():
    init_traceback()
    fancy_intro(log)
    loop = asyncio.get_event_loop()
    task = loop.create_task(process_modpack_config())
    loop.run_until_complete(task)
    save_lockfile()
    sys.exit()


if __name__ == '__main__':
    main()
