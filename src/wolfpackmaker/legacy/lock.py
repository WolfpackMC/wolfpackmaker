import io
import os
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
from rich.traceback import install as init_traceback
from util import Log

TYPE_FABRIC = 4
TYPE_FORGE = 1


log = Log()

found_mods = []
mod_slugs = []


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
    parser.add_argument('--with-figlet', help='Defaults to True. Use Figlet when printing the wolfpackmaker intro')
    return parser

timeout = aiohttp.ClientTimeout(total=1)
retries = 5

async def fetch_file(curseforge_url, mod, session, fileId):
    files_url = f"{curseforge_url}{mod['id']}/file/{fileId}"
    for i in range(retries):
        try:
            async with session.get(files_url, timeout=timeout) as r:
                try:
                    file = await r.json()
                except ContentTypeError:
                    log.error(mod)
                    sys.exit(log.error("ContentType error."))
            break
        except asyncio.TimeoutError:
            log.info(f"Retrying {mod['name']} ({i+1} of {retries})...")
            continue
    return file


async def set_content_length(curseforge_url, session, mod_slug):
    async with session.get(curseforge_url) as r:
        content_length = int()
        try:
            content_length = int(r.headers['content-length'])
        except KeyError:
            log.warning("Could not get Content-Length directly, getting it ourselves...")
            async for chunk in r.content.iter_any():
                content_length += len(chunk)
            log.info(content_length)

    for m in found_mods:
        if mod_slug == m['slug']:
            log.info(f"Appended file length to {m['name']}")
            m.update({"fileLength": content_length})


async def fetch_mod(curseforge_url, mod_id, session):
    mod_url = curseforge_url + str(mod_id)
    for i in range(retries):
        try:
            async with session.get(mod_url, timeout=timeout) as r:
                # log.debug("Responding to request {}...".format(mod_url))
                try:
                    mod = await r.json()
                except ContentTypeError:
                    sys.exit(log.error("ContentType error."))
            break
        except asyncio.TimeoutError:
            log.info(f"Retrying {mod_id['name']}...")
            continue
    return mod


modloader = ''

import datetime


async def get_mod_file(curseforge_url, modpack_manifest, version, mc_version, mod, session, is_file_found):
    if is_file_found:
        return
    try:
        mod_compat = version["modLoader"]
    except KeyError:
        mod_compat = None
    
    if modpack_manifest["modloader"].lower() == 'forge' and mod_compat == TYPE_FABRIC:
        return
    if modpack_manifest["modloader"].lower() == 'fabric' and mod_compat == TYPE_FORGE:
        return
    if version["gameVersion"] in mc_version:
        file_id = version["projectFileId"]
        file = await fetch_file(curseforge_url, mod, session, file_id)
        return file


async def fetch_mod_data(curseforge_url, mod, session, modpack_manifest, cf_data, completed, to_complete):
    start_time = time.time()
    mc_version = [modpack_manifest["version"]]
    # if "1.16.5" in mc_version:
    #     for i in range(1, 5):
    #         mc_version.append(f"1.16.{i}")
    file_found = False

    try:
        latest_files = mod['latest_files']
    except KeyError:
        try:
            latest_files = mod['gameVersionLatestFiles']
        except KeyError:
            log.info(mod)
            latest_files = mod['latestFiles']
    
    for version in latest_files:
            file = await get_mod_file(curseforge_url, modpack_manifest, version, mc_version, mod, session, file_found)
            if not file: continue
            file_found = True
            deps = []
            for dep in file["dependencies"]:
                if dep["addonId"] in [m["id"] for m in found_mods]:
                    break
                deps += [d for d in cf_data if dep["addonId"] == d["id"] and dep["type"] == 3]
            dep_file_found = False
            for d in deps:
                if d['slug'] in [m for m in mod_slugs]:
                    break
                log.info(f"Resolving dependency {d['name']} for mod {mod['name']}...")
                mod_slugs.append(d['slug'])
                for df in d["latest_files"]:
                    dep_file = await get_mod_file(curseforge_url, modpack_manifest, df, mc_version, d, session, dep_file_found)
                    if not dep_file: continue
                    dep_file_found = True
                    found_mods.append({
                        "id": d["id"],
                        "slug": d["slug"],
                        "name": d["name"],
                        "downloadUrl": dep_file["downloadUrl"],
                        "filename": dep_file["fileName"],
                        "fileLength": dep_file["fileLength"]
                    })
            for m in found_mods:
                if m.get('downloadUrl') is not None:
                    continue
                if m["id"] == mod["id"]:
                    m.update({'downloadUrl': file['downloadUrl'], 'filename': file['fileName'], 'fileLength': file['fileLength']})
    completed[0] += 1
    log.info(f"[LOCK] [{completed[0]}/{to_complete[0]}] {mod['name']} took {time.time() - start_time:.3f} seconds.")
    if not file_found:
        log.warning(
            f"Mod {mod['slug']} [{mod['name']}] does not have an apparent version for {mc_version}, tread with caution")

minecraft_version = []

async def process_modpack_config(manifest):
    chunked = True  # Should chunk
    curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/'
    modpack_manifest = yaml.load(manifest, Loader=yaml.SafeLoader)
    minecraft_version.append(modpack_manifest["version"])
    mods = modpack_manifest["mods"]
    # check for duplicates
    duplicate_mods = []
    for idx, mod in enumerate(mods):
        for k, v in mods[idx].items():
            mod_slugs.append(k)
            duplicate_mods.append(k)
    if [k for k,v in Counter(duplicate_mods).items() if v>1]:
        sys.exit(log.critical(f"Found duplicates in the manifest file. Please remove them before continuing:\n> {[k for k,v in Counter(duplicate_mods).items() if v>1]}"))
    curseforge_download_url = "https://vulpera.com/curseforge.json"
    session = aiohttp.ClientSession()
    log.debug(f"Established session {session}")
    log.info(f"Reading CurseForge data from {curseforge_download_url}")
    start_time = time.time()
    async with session.get(curseforge_download_url) as r:
        date = datetime.datetime.strptime(r.headers["last-modified"], "%a, %d %b %Y %H:%M:%S %Z")
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
            custom = [False]
            has_id = [False]
            match v:
                case {'id': id}:
                    try:
                        mod_data["filename"]
                    except KeyError:
                        to_complete[0] += 1
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
                        has_id[0] = True
                case {'url': url}:
                    task = asyncio.create_task(set_content_length(url, session, k))
                    tasks.append(task)
                    if url.split('.')[-1] == 'zip':
                        log.info(f"Handling resourcepack {k}...")
                        found_mods.append({
                            "id": mod_data['id'] or None,
                            "name": k,
                            "slug": k,
                            "filename": basename(url),
                            "downloadUrl": url,
                            "resourcepack": True
                        })
                        continue
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
                        "custom": True,
                    })
                    to_complete[0] += 1
                    completed[0] += 1
                    log.info(f"[LOCK] [{completed[0]}/{to_complete[0]}] Resolved {mod_data['name']}, using custom URL {url}")
                    custom[0] = True
            if has_id[0]: continue
            if custom[0]: continue
            to_complete[0] += 1
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
    await asyncio.gather(*tasks)
    await session.close()
    return found_mods


def save_lockfile():
    log.info("Saving lockfile...")
    with open('manifest.lock', 'w') as f:
        f.write(json.dumps({"version": minecraft_version[0], "mods": found_mods}))
    log.info("Saving pretty-printed file...")
    with open('manifest.json', 'w') as f:
        f.write(json.dumps({"version": minecraft_version[0], "mods": found_mods}, indent=2))

import requests

import sys

from rich import inspect

def main():
    init_traceback()
    parser = init_args()
    args = parse_args(parser)
    log.parse_log(args)
    log.fancy_intro(parser.description)
    loop = asyncio.new_event_loop()
    if args.manifest:
        if 'yml' and not 'https' in args.manifest:
            args.manifest = open(args.manifest).read()
        elif 'https' and 'yml' in args.manifest:
            args.manifest = requests.get(args.manifest).text
    else:
        if os.path.exists('manifest.yml'):
            with open('manifest.yml') as f:
                args.manifest = f.read()
    task = loop.create_task(process_modpack_config(manifest=args.manifest))
    loop.run_until_complete(task)
    save_lockfile()
    log.save_log("lock")
    sys.exit()


if __name__ == '__main__':
    main()
