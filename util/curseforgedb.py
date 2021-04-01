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


def fancy_intro(log):
    f = Figlet().renderText("woofmc.xyz")
    log.info(str('').join(['####' for _ in range(16)]))
    log.info(f)
    log.info(str('').join(['####' for _ in range(16)]))


async def get_curseforge_api(session, index, page_size, log):
    curseforge_url = 'https://addons-ecs.forgesvc.net/api/v2/addon/search?gameId=432&sectionId=6&sortDescending=true' \
                     '&sort=\'Featured\' '
    async with session.get(curseforge_url + '&pageSize={}&index={}'.format(page_size, index)) as r:
        log.debug("Requesting CurseForge API starting from index {}...".format(index))
        return await r.json()


async def process_curseforge_db(log):
    index = 0
    page_size = 1000
    # we could normally while True this, but CurseForge API stops at 9999 (from 0, so 10000 mods each run)
    # this is more than plenty, but should a custom mod be read it may as well be requested in the lock script
    # we are sorting mods by featured, so this is hopefully a seldom issue
    session = aiohttp.ClientSession()
    workers = []
    mods = []
    for i in range(10):  # each loop we add 1000 to the index, to basically flip a page in the API
        workers.append(asyncio.create_task(get_curseforge_api(session, index, page_size, log)))
        index += page_size
    for task in asyncio.as_completed(workers):
        mod_data = await task
        for m in mod_data:
            mods.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "slug": m.get("slug")
            })
    await session.close()
    with open('curseforge.db', 'w') as f:
        log.debug("Saving mod data...")
        f.write(json.dumps(mods))


def main():
    init_traceback()
    log = logging.getLogger("rich")
    fancy_intro(log)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_curseforge_db(log))


if __name__ == '__main__':
    main()
