import requests

from os import remove
from os.path import getsize, dirname, realpath
from rich.traceback import install as init_traceback
import asyncio

self_file = requests.get("https://raw.githubusercontent.com/WolfpackMC/wolfpackmaker/master/src/wolfpackmaker/wolfpackmaker.py", headers={'User-Agent': 'kalka.io'})
util_file = requests.get("https://raw.githubusercontent.com/WolfpackMC/wolfpackmaker/master/src/wolfpackmaker/util.py", headers={'User-Agent': 'kalka.io'})

file_path = dirname(__file__)

if len(self_file.content) != getsize(f"{file_path}/wolfpackmaker/wolfpackmaker.py"):
    print("Updating wolfpackmaker.py...")
    with open(realpath(f"{file_path}/wolfpackmaker/wolfpackmaker.py"), 'wb') as f:
         f.write(self_file.content)
if len(util_file.content) != getsize(f"{file_path}/wolfpackmaker/util.py"):
    print("Updating util.py...")
    with open(realpath(f"{file_path}/wolfpackmaker/util.py"), 'wb') as f:
         f.write(util_file.content)

from wolfpackmaker.wolfpackmaker import Wolfpackmaker, get_spinner

if __name__ == "__main__":
    w = Wolfpackmaker()
    init_traceback(console=w.log)
    w.main()
    w.create_folders()
    w.log.fancy_intro(description=f"Wolfpackmaker / {Wolfpackmaker.VERSION}")
    w.loop = asyncio.new_event_loop()
    try:
        w.loop.run_until_complete(
            w.get_mods(w.args.clientonly, w.args.serveronly)
        )
    except KeyboardInterrupt:
        try:
            w.progress.update(w.progress_task, description=f"[red]{w.progress_task.description}")
        except AttributeError:
            pass
        w.log.info("Canceling!")
        try:
            w.log.info(f"Flagging {w.current_mod} for deletion as it was in the middle of being downloaded")
            try:
                remove(f"{w.mods_dir}/{w.current_mod}")
            except FileNotFoundError:
                pass
            try:
                remove(f"{w.mods_cache_dir}/{w.current_mod}")
            except FileNotFoundError:
                pass
        except AttributeError:
            pass
    if not w.args.noninteractive:
        optifine_confirm = input("Would you like to install OptiFine? (y/N): ") == 'y' and True or False
        if optifine_confirm:
            from rich import inspect
            inspect(w.minecraft_version)
            #w.loop.run_until_complete(w.save_mod("Optifine", download_url, get_spinner(), "Optifine"))
    w.log.info("We're done here.")
    w.log.save_log("wolfpackmaker")