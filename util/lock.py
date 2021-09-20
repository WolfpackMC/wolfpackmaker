import aiohttp
import argparse
import asyncio
import datetime
import json
import logging
import sys
import yaml

from os.path import basename
from rich.logging import RichHandler
from aiohttp.client_exceptions import ContentTypeError
from rich.traceback import install as init_traceback
from pyfiglet import Figlet

TYPE_FABRIC = 4
TYPE_FORGE = 1

# noinspection PyArgumentList
logging.basicConfig(
    level=logging.DEBUG, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("rich")

found_mods = []


def fancy_intro():
    f = Figlet().renderText("woofmc.xyz")
    log.info(str('').join(['####' for _ in range(16)]))
    log.info(f)
    log.info(str('').join(['####' for _ in range(16)]))


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
        # log.debug("Responding to request {}...".format(files_url))
        try:
            file = await r.json()
        except ContentTypeError:
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


async def fetch_mod_data(curseforge_url, mod, session, modpack_manifest):
    mc_version = [modpack_manifest.get("version")]
    if "1.16.5" in mc_version:
        for i in range(1, 5):
            mc_version.append(f"1.16.{i}")
    file_found = False
    for version in mod.get("latest_files"):
        mod_compat = version.get("modLoader")
        if modpack_manifest.get("modloader").lower() == 'forge' and mod_compat == TYPE_FABRIC:
            continue
        if modpack_manifest.get("modloader").lower() == 'fabric' and mod_compat == TYPE_FORGE:
            continue
        if file_found:
            continue
        if version.get("gameVersion") in mc_version:
            file_id = version.get("projectFileId")
            file = await fetch_file(curseforge_url, mod, session, file_id)
            for m in found_mods:
                if m.get("slug") == mod.get("slug"):
                    log.debug("Adding {} to the manifest from mod {}".format(file.get("downloadUrl"),
                                                                             mod.get("name")))
                    m.update({"downloadUrl": file.get("downloadUrl"), "filename": file.get("fileName")})
            file_found = True
            for dependencies in file.get("dependencies"):
                if dependencies.get("type") == 3:
                    dependency_mod = await fetch_mod(curseforge_url, dependencies.get("addonId"), session)
                    manifest_mods = [list(mod.keys()) for mod in modpack_manifest.get("mods")]
                    found = False
                    for m in manifest_mods:
                        if dependency_mod.get("slug") == str().join(m) or dependency_mod.get("slug") in [mod.get("slug")
                                                                                                         for mod in
                                                                                                         found_mods]:
                            found = True
                            break
                    if found:
                        continue
                    log.debug(
                        "Resolving dependency: {} ({}) for mod {}".format(
                            dependency_mod.get("slug"),
                            dependency_mod.get("name"),
                            mod.get("slug")
                        ))
                    # double check to make sure we don't have a duplicate
                    dependency_file = await fetch_file(curseforge_url, mod, session, file_id)
                    found_mods.append({
                        "id": dependency_mod.get("id"),
                        "slug": dependency_mod.get("slug"),
                        "name": dependency_mod.get("name"),
                        "downloadUrl": dependency_file.get("downloadUrl"),
                        "filename": dependency_file.get("fileName")})
                    # log.debug(dependency_file)
                    for m in found_mods:
                        if m.get("slug") == mod.get("slug"):
                            log.debug("Adding {} to the manifest from mod {}".format(file.get("downloadUrl"),
                                                                                     mod.get("name")))
                            m.update({"downloadUrl": file.get("downloadUrl"), "filename": file.get("fileName")})
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
    session = aiohttp.ClientSession()
    log.debug(f"Established session {session}")
    with open(args.manifest or 'manifest.yml', 'r') as f:
        modpack_manifest = yaml.load(f.read(), Loader=yaml.SafeLoader)

    curseforge_download_url = "https://get.kalka.io/curseforge.json"

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
    mods = modpack_manifest.get("mods")
    tasks = []
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
                    log.info("Resolved {} as {} in the local database! [{}] [{}]".format(k,
                                                                                         m.get("slug"),
                                                                                         m.get("name"),
                                                                                         m.get("id")))
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
                    task = asyncio.create_task(fetch_mod_data(curseforge_url, m, session, modpack_manifest))
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

                        log.warning("{} was not found{}".format(k,
                                                                 '.' if not args.nomodleftbehind else ', looking manually...'))
                        if id:
                            log.info(f"Using {id} for {k}...")
                            cf_get = await session.get(curseforge_url + str(id))
                            data = await cf_get.json()
                            log.info("Resolved {} as {} through CurseForge! [{}] [{}]".format(k,
                                                                                                 data.get("slug"),
                                                                                                 data.get("name"),
                                                                                                 data.get("id")))
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
                        found_mods.append({
                            "id": mod_found.get("id"),
                            "slug": mod_found.get("slug"),
                            "name": mod_found.get("name"),
                            "clientonly": clientonly,
                            "serveronly": serveronly,
                            "optional": optional
                        })
                        task = asyncio.create_task(fetch_mod_data(curseforge_url, mod_found, session, modpack_manifest))
                        tasks.append(task)
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
    fancy_intro()
    loop = asyncio.get_event_loop()
    task = loop.create_task(process_modpack_config())
    loop.run_until_complete(task)
    save_lockfile()
    sys.exit()


if __name__ == '__main__':
    main()
