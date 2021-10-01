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
    
    for version in mod.get("latest_files"):
            file = await get_mod_file(curseforge_url, modpack_manifest, version, mc_version, mod, session, file_found)
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
    log.info(f"[{completed[0]}/{to_complete[0]}] {mod.get('name')} took {time.time() - start_time:.3f} seconds.")
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
    async with session.get(curseforge_download_url) as r:
        date = datetime.datetime.strptime(r.headers.get("last-modified"), "%a, %d %b %Y %H:%M:%S %Z")
        log.info(f"CurseForge DB date is {datetime.datetime.strftime(date, '%B %d, %Y at %H:%M:%Sz')}")
        if chunked:
            log.info("Reading chunked data... (it's probably big)")
            data = bytes()
            async for c in r.content.iter_chunked(65535):
                data += c
        else:
            data = await r.read()
        curseforge_data = json.loads(data)
    tasks = []
    to_complete = [0]
    completed = [0]
    from rich import inspect
    for idx, mod in enumerate(mods):
        for k, v in mods[idx].items():
            found = False
            if v is not None:
                try:
                    custom_url = v.get("url")
                except AttributeError:
                    custom_url = None
                if custom_url is not None:
                    found_id = None
                    found_name = k
                    for m in curseforge_data:
                        # Double-check if the custom URL exists in curseforge DB, but DON'T push download data
                        if k == m.get("slug"):
                            found_id = m.get("id")
                            found_name = m.get("name")
                            found_slug = m.get("slug")
                    clientonly = False
                    serveronly = False
                    optional = False
                    if v.get("optional"):
                        optional = True
                    if v.get("clientonly"):
                        clientonly = True
                    if v.get("serveronly"):
                        serveronly = True
                    found_mods.append({
                        "id": found_id or None,
                        "name": found_name or k,
                        "slug": k,
                        "filename": '=' in v.get("url") and v.get("url").split("=")[1] or basename(v.get("url")),
                        "downloadUrl": v.get("url"),
                        "clientonly": clientonly,
                        "serveronly": serveronly,
                        "optional": optional,
                        "custom": True
                    })
                    log.info(f"Using custom URL {v.get('url')} for mod {found_name}" + (
                                found_id and f" (found in Curseforge DB as {found_name})" or ""))
            for m in curseforge_data:
                try:
                    custom_url = v.get("url")
                except AttributeError:
                    custom_url = None
                if k == m.get("slug") and custom_url is None:
                    log.info(f"Resolved {m.get('name')}! [{m.get('slug')}] [{m.get('id')}]")
                    found = True
                    optional = False
                    clientonly = False
                    serveronly = False
                    if v is not None:
                        if v.get("optional"):
                            optional = True
                        if v.get("clientonly"):
                            clientonly = True
                        if v.get("serveronly"):
                            serveronly = True
                    found_mods.append({
                        "id": m.get("id"),
                        "slug": m.get("slug"),
                        "name": m.get("name"),
                        "clientonly": clientonly,
                        "serveronly": serveronly,
                        "optional": optional
                    })
                    task = asyncio.create_task(fetch_mod_data(curseforge_url, m, session, modpack_manifest, curseforge_data, completed, to_complete))
                    tasks.append(task)
            if not found:
                try:
                    custom_url = v.get("url")
                    optional = v.get("optional")
                    clientonly = v.get("clientonly")
                    serveronly = v.get("serveronly")
                    id = v.get("id")
                except AttributeError:
                    clientonly = False
                    serveronly = False
                    custom_url = None
                    optional = None
                    id = None
                if not custom_url:
                    if args.nomodleftbehind:
                        if id:
                            log.info(f"Using {id} for {k}. This should guarantee a positive match.")
                            cf_get = await session.get(curseforge_url + str(id))
                            data = await cf_get.json()
                            if k != data.get("slug"):
                                sys.exit(log.critical(f"Mod mismatch! {k} =/= {data.get('slug')}. This is usually impossible unless you are using the wrong mod ID."))
                            log.info(f"Resolved {k} as {data.get('slug')} through CurseForge! [{data.get('name')}] [{data.get('id')}]")
                            found = True
                            mod_found = {
                                "id": data.get("id"),
                                "slug": data.get("slug"),
                                "name": data.get("name"),
                                "latest_files": data.get("gameVersionLatestFiles")
                            }
                        else:
                            mod_found = await search_mod(curseforge_url, k, session)
                        if mod_found is None:
                            log.critical(f'{k} was not found in CurseForge API. Sorry.')
                            log.critical(f'This happened because we exhausted all efforts to search for {k}, and the only info we know about it is the mod slug, which is just {k}. The easiest fix to this is to visit https://www.curseforge.com/minecraft/mc-mods/{k} and copy the value of "Project ID", and append it to the corresponding mod in the yaml manifest, e.g:\n- {k}:\n    id: <id>... \nThe script will continue and disregard this specific mod, but it will be considered a mod we cannot digest!')
                            to_complete[0] -= 1
                            continue
                        found_mods.append({
                            "id": mod_found.get("id"),
                            "slug": mod_found.get("slug"),
                            "name": mod_found.get("name"),
                            "clientonly": clientonly,
                            "serveronly": serveronly,
                            "optional": optional
                        })
                        task = asyncio.create_task(fetch_mod_data(curseforge_url, mod_found, session, modpack_manifest, curseforge_data, completed, to_complete))
                        tasks.append(task)
            if found:
                to_complete[0] += 1
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
