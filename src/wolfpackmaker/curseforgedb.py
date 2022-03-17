import aiohttp
import argparse
import asyncio
import json
from rich.traceback import install as init_traceback
from util import Log


def parse_args(parser):
    args = parser.parse_args()
    return args


def init_args():
    parser = argparse.ArgumentParser(
        description='Wolfpackmaker (curseforgedb.py) (https://woofmc.xyz)'
    )
    parser.add_argument('--with-figlet', help='Defaults to True. Use Figlet when printing the wolfpackmaker intro')
    parser.add_argument("-v", "--verbose", action="store_true",
                            help="increase output verbosity")
    return parser


parser = init_args()
args = parse_args(parser)

headers = {'User-Agent':'wolfpackmaker (made by Kalka) business inquiries: b@kalka.io'}


async def get_curseforge_api(session, index, page_size, log, version=None):
    curseforge_url = f'https://addons-ecs.forgesvc.net/api/v2/addon/search?categoryId=0&gameId=432{version and "&gameVersion=" + str(version)}&sectionId=6&searchFilter=&sort=0'
    async with session.get(curseforge_url + '&pageSize={}&index={}'.format(page_size, index)) as r:
        data = await r.json()
        log.debug("Requested CurseForge API starting from index {}{}.".format(index,
                                                                                 version and ' for version ' + version or ''))
        return data

versions = [
    "1.16.5",
    "1.16.4",
    "1.16.3",
    "1.16.2",
    "1.16.1",
    "1.16",
    "1.12.2",
    "1.7.10"
]


async def process_curseforge_db(log):
    assert isinstance(log, Log)
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
            if m['id'] in [v['id'] for v in mods]:
                continue
            mods.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "summary": m.get("summary"),
                "slug": m.get("slug"),
                "latest_files": m.get("gameVersionLatestFiles") or m.get("latest_files") or m.get("latestFiles")
            })
    log.info(f"{len(mods)} mods.")
    await session.close()
    with open('curseforge.json', 'w') as f:
        log.debug("Saving mod data...")
        f.write(json.dumps(mods, indent=2))


def main():
    init_traceback()
    log = Log()
    log.parse_log(args)
    log.fancy_intro("Wolfpackmaker / curseforgedb.py")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_curseforge_db(log))


if __name__ == '__main__':
    main()
