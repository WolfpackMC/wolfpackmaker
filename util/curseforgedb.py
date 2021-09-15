import aiohttp
import asyncio
import json
import logging

from pyfiglet import Figlet
from rich.logging import RichHandler
from rich.traceback import install as init_traceback

# noinspection PyArgumentList
logging.basicConfig(
    level=logging.DEBUG, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

headers = {'User-Agent':'wolfpackmaker/0.3.0 (made by Kalka) business inquiries: b@kalka.io'}


def fancy_intro(log):
    f = Figlet().renderText("woofmc.xyz")
    log.info(str('').join(['####' for _ in range(16)]))
    log.info(f)
    log.info(str('').join(['####' for _ in range(16)]))


async def get_curseforge_api(session, index, page_size, log, version=None):
    curseforge_url = f'https://addons-ecs.forgesvc.net/api/v2/addon/search?categoryId=0&gameId=432{version and "&gameVersion=" + str(version)}&sectionId=6&searchFilter=&sort=0'
    async with session.get(curseforge_url + '&pageSize={}&index={}'.format(page_size, index)) as r:
        data = await r.json()
        log.debug("Requested CurseForge API starting from index {}{}.".format(index,
                                                                                 version and ' for version ' + version or ''))
        return data

versions = [
    "1.16.5",
    "1.12.2",
    "1.7.10"
]


async def process_curseforge_db(log):
    index = 0
    page_size = 50
    session = aiohttp.ClientSession()
    workers = []
    mods = []
    for i in range(200):
        workers.append(asyncio.create_task(get_curseforge_api(session, index, page_size, log)))
        index += page_size
    for v in versions:
        index = 0
        page_size = 50
        for i in range(200):
            workers.append(asyncio.create_task(get_curseforge_api(session, index, page_size, log, version=v)))
            index += page_size
    future = asyncio.gather(*workers)
    for d in await future:
        for m in d:
            if m.get("id") in [v.get("id") for v in mods]:
                continue
            mods.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "summary": m.get("summary"),
                "slug": m.get("slug"),
                "latest_files": m.get("gameVersionLatestFiles")
            })
    log.info(f"{len(mods)} mods.")
    await session.close()
    with open('curseforge.json', 'w') as f:
        log.debug("Saving mod data...")
        f.write(json.dumps(mods, indent=2))


def main():
    init_traceback()
    log = logging.getLogger("rich")
    fancy_intro(log)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_curseforge_db(log))


if __name__ == '__main__':
    main()
