import aiohttp
import asyncio
import datetime
import json
import logging
import sys
import yaml

from os.path import basename
from rich.logging import RichHandler
from rich.traceback import install as init_traceback
from pyfiglet import Figlet

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


async def sort_files(files, mod, modpack_manifest):
    filtered_file_data = []
    found = False
    acceptable_versions = [modpack_manifest.get("version")]
    for f in files:
        if modpack_manifest.get("modloader") == 'Forge' and 'Fabric' in f.get("gameVersion"):
            continue
        if modpack_manifest.get("modloader") == 'Fabric' and 'Forge' in f.get("gameVersion"):
            continue

        # The following is a hacky method to allow fuzziness for 1.16.5 versions.
        # e.g If the modpack on CurseForge is displayed as "1.16.4" even though it's compatible for 1.16.5
        # This is usually an author error, when they either forget to update the file to support the 1.16.5 tag, or just
        # don't care enough.
        if modpack_manifest.get("version") == "1.16.5" and modpack_manifest.get("version") not in f.get("gameVersion"):
            for i in range(1,5):
                string = '1.16.{}'.format(i)
                if string in f.get("gameVersion"):
                    f.get("gameVersion").append(modpack_manifest.get("version"))

        if modpack_manifest.get("version") not in f.get("gameVersion"):
            continue
        # log.debug("Found {} for {} with a date of {}".format(f.get("displayName"), mod.get("slug"), f.get("fileDate")))
        found = True
        filtered_file_data.append(f)
    if not found:
        log.critical(
            "We couldn't find a download file for {}"
            ". Possible {} mod?".format(mod.get("slug"),
                                        ('Fabric' if 'Forge' in modpack_manifest.get("modloader") else 'Forge')))
        sys.exit(1)
    dates = []
    for date in filtered_file_data:
        try:
            file_date = datetime.datetime.strptime(date.get("fileDate"), '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            file_date = datetime.datetime.strptime(date.get("fileDate"), '%Y-%m-%dT%H:%M:%S%z')
        dates.append(file_date)
    filtered_file = {}
    for f in filtered_file_data:
        try:
            file_date = datetime.datetime.strptime(f.get("fileDate"), '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            file_date = datetime.datetime.strptime(f.get("fileDate"), '%Y-%m-%dT%H:%M:%S%z')
        if not file_date == max(dates):
            continue
        # log.debug("Using {} as the filedate for {}".format(file_date, mod.get("name")))
        filtered_file.update(f)
    return filtered_file


async def fetch_files(curseforge_url, mod, session):
    files_url = curseforge_url + '{}/files'.format(mod.get("id"))
    async with session.get(files_url) as r:
        # log.debug("Responding to request {}...".format(files_url))
        files = await r.json()
    return files


async def fetch_mod(curseforge_url, mod_id, session):
    mod_url = curseforge_url + str(mod_id)
    async with session.get(mod_url) as r:
        # log.debug("Responding to request {}...".format(mod_url))
        mod = await r.json()
    return mod


async def fetch_mod_data(curseforge_url, mod, session, modpack_manifest):
    files = await fetch_files(curseforge_url, mod, session)
    # log.debug("Checking for dependencies...")
    filtered_file = await sort_files(files, mod, modpack_manifest)
    for dependencies in filtered_file.get("dependencies"):
        if dependencies.get("type") == 3:
            if dependencies.get("addonId") in (m.get("id") for m in found_mods):
                # log.debug("Dependency already found")
                continue
            else:
                dependency_mod = await fetch_mod(curseforge_url, dependencies.get("addonId"), session)
                log.debug(
                    "Resolving dependency: {} ({}) for mod {}".format(
                        dependency_mod.get("slug"),
                        dependency_mod.get("name"),
                        mod.get("slug")
                    ))
                dependency_file = await sort_files(
                    await fetch_files(curseforge_url, dependency_mod, session), dependency_mod, modpack_manifest)
                found_mods.append({
                    "id": dependency_mod.get("id"),
                    "slug": dependency_mod.get("slug"),
                    "name": dependency_mod.get("name"),
                    "downloadUrl": dependency_file.get("downloadUrl"),
                    "filename": dependency_file.get("fileName")})
                # log.debug(dependency_file)
    for m in found_mods:
        if m.get("id") == mod.get("id"):
            m.update({"downloadUrl": filtered_file.get("downloadUrl"), "filename": filtered_file.get("fileName")})


async def process_modpack_config():
    curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/'
    with open('test.yml', 'r') as f:
        modpack_manifest = yaml.load(f.read(), Loader=yaml.SafeLoader)
    with open('curseforge.db', 'r') as f:
        curseforge_data = json.loads(f.read())
    mods = modpack_manifest.get("mods")
    session = aiohttp.ClientSession()
    tasks = []
    for idx, mod in enumerate(mods):
        for k, v in mods[idx].items():
            found = False
            if v is not None:
                custom_url = v.get("url")
                if custom_url is not None:
                    log.info("Using custom URL {} for mod {}".format(k, custom_url))
                    for m in curseforge_data: # Double-check if the custom URL exists in curseforge DB (It's messy, I know)
                        if k == m.get("slug"):
                            found_id = m.get("id")
                            found_name = m.get("name")
                    found_mods.append({
                        "id": found_id,
                        "name": found_name,
                        "slug": k,
                        "filename": basename(custom_url),
                        "downloadUrl": custom_url,
                        "clientonly": clientonly,
                        "serveronly": serveronly
                    })
                    break
            for m in curseforge_data:
                if k == m.get("slug"):
                    log.info("Resolved {} as {} in the local database! [{}] [{}]".format(k,
                                                                                         m.get("slug"),
                                                                                         m.get("name"),
                                                                                         m.get("id")))
                    found = True
                    clientonly = False
                    serveronly = False
                    if v is not None:
                        if v.get("clientonly"):
                            clientonly = True
                        if v.get("serveronly"):
                            serveronly = True
                    found_mods.append({
                        "id": m.get("id"),
                        "slug": m.get("slug"),
                        "name": m.get("name"),
                        "clientonly": clientonly,
                        "serveronly": serveronly
                    })
                    task = asyncio.create_task(fetch_mod_data(curseforge_url, m, session, modpack_manifest))
                    tasks.append(task)
            if not found:
                try:
                    custom_url = v.get("url")
                    clientonly = v.get("clientonly")
                    serveronly = v.get("serveronly")
                except AttributeError:
                    clientonly = False
                    serveronly = False
                    custom_url = None
                if not custom_url:
                    log.critical("{} was not found".format(k))
    await asyncio.gather(*tasks)
    await session.close()


def save_lockfile():
    log.info("Saving lockfile...")
    with open('manifest.lock', 'w') as f:
        f.write(json.dumps(found_mods))


def main():
    init_traceback()
    fancy_intro()
    loop = asyncio.get_event_loop()
    task = loop.create_task(process_modpack_config())
    loop.run_until_complete(task)
    save_lockfile()


if __name__ == '__main__':
    main()
