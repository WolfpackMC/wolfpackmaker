import argparse
import aiohttp
import asyncio
import time
import json
import urllib3
import sys

from os import path

from util import Log


class ModList:
    author = "WolfpackMC"
    repo = ""

    curseforge_url = "https://addons-ecs.forgesvc.net/api/v2/addon/"
    github_url = "https://api.github.com/repos/{}/{}/releases"
    mod_list = []


    async def fetch(self, session, url):
        try:
            async with session.get(url) as r:
                r = await r.read()
        except aiohttp.ClientResponseError as e:
            self.log.warning(e.code)
        except asyncio.TimeoutError:
            self.log.warning("Timeout")
        except Exception as e:
            self.log.warning(e)
        else:
            return r
        return


    async def fetch_async(self, loop, mods):
        tasks = []
        # try to use one client session
        async with aiohttp.ClientSession() as session:
            for m in mods:
                project_id = m.get("id")
                if project_id is not None:
                    task = asyncio.ensure_future(self.fetch(session, self.curseforge_url + str(project_id)), loop=loop)
                    tasks.append(task)
            # await response outside the for loop
            responses = await asyncio.gather(*tasks)
        return responses


    def get_github_data(self):  # single threaded, not needed to be intensive
        if path.exists('manifest.lock'):
            self.log.info("Found local manifest.lock. Using that instead.")
            with open('manifest.lock', 'r') as f:
                mod_data_json = json.loads(f.read())
            self.log.info("Done.")
        else:
            self.log.info("Local packmaker not found, grabbing from the URL.")
            http = urllib3.PoolManager()
            self.repo = self.args.repo
            r = http.request('GET', self.github_url.format(self.author, self.repo))
            data = json.loads(r.data)
            mod_data_url = data[0]["assets"][1]["browser_download_url"]
            mod_data = http.request('GET', mod_data_url)
            mod_data_json = json.loads(mod_data.data)
        return mod_data_json["mods"]


    def get_logo(self, attachments):
        for attachment in attachments:
            if attachment['isDefault']:
                return attachment['thumbnailUrl']


    def main(self):
        self.log = Log()
        self.parse = argparse.ArgumentParser(description="Wolfpackmaker / raw_mod_list.py")
        self.parse.add_argument("-v", "--verbose", action="store_true",
                    help="increase output verbosity")
        self.parse.add_argument("-r", "--repo", help="Repo name to search for and generate a mod list description of.")
        self.args = self.parse.parse_args()
        self.log.parse_log(self.args)
        self.log.fancy_intro(self.parse.description)
        self.log.info("Awoo!")
        start_time = time.time()
        loop = asyncio.new_event_loop()
        mods = self.get_github_data()
        future = asyncio.ensure_future(self.fetch_async(loop, mods), loop=loop)
        loop.run_until_complete(future)
        responses = future.result()
        self.log.info(f"Requests took {time.time() - start_time} seconds.")
        start_time = time.time()
        self.data = []
        for r in responses:
            json_response = json.loads(r)
            try:
                author = json_response.get("authors")[0]
            except IndexError:
                author = {
                    "name": "Unknown",
                    "url": "Unknown"
                }
            clean_data = {
                "id": json_response.get("id"),
                "name": json_response.get("name"),
                "summary": json_response.get("summary"),
                "website_url": json_response.get("websiteUrl"),
                "logo": self.get_logo(json_response.get("attachments", {})),
                "slug": json_response.get("slug"),
                "author": author.get("name"),
                "author_url": author.get("url"),
                "download_count": json_response.get("downloadCount")
            }
            self.data.append(clean_data)

        self.sort_mods()

        self.save_modlist()

        self.log.info(f"Sorting data and saving modlist took {time.time() - start_time} seconds.")

    def sort_mods(self):
        self.log.info("Sorting mods...")
        self.data = sorted(self.data, key = lambda i: i['download_count'], reverse=True)


    def save_modlist(self):
        with open('modlist.json', 'wb') as f:
            b = bytes(json.dumps(self.data), encoding='utf8')
            f.write(b)


def main():
    mods = ModList()
    mods.main()


main()
    
