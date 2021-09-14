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

import time

async def get_curseforge_api(session, index, page_size, log):
    log.debug("Requesting CurseForge API starting from index {}...".format(index))
    curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/search?gameId=432&sectionId=6&sortDescending=true' \
                     '&sort=\'Featured\' '
    async with session.get(curseforge_url + '&pageSize={}&index={}'.format(page_size, index)) as r:
        data = await r.json()
        await asyncio.sleep(0.5)
        return data


async def process_curseforge_db(log):
    index = 0
    page_size = 50
    session = aiohttp.ClientSession()
    workers = []
    mods = []
    for i in range(200):
        workers.append(asyncio.create_task(get_curseforge_api(session, index, page_size, log)))
        index += page_size
    future = asyncio.gather(*workers)
    for d in await future:
        for m in d:
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
