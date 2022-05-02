import os
import shutil
from os.path import exists, join

from tinydb import TinyDB, Query


class MultiMC:
    def __init__(self, wolfpackinst):
        wfi = wolfpackinst
        if exists(join(wfi.current_dir, "mmc-pack.json")):
            valid = True
        else:
            valid = False

        if not valid:
            wfi.log.warn(f"{wfi.current_dir} does not have a valid MultiMC json file. Ensure this is the directory you "
                         f"are intending to use with MultiMC.")
            return

        if wfi.args.dir:
            confirm = input(f"Are you sure you want to install {' '.join(wfi.modpack_name.split('-')).title()} into {wfi.current_dir}? (y/n): ")
            if confirm == 'y':
                pass
            elif confirm == 'n':
                return
            else:
                return

        multimc_dir = join(wfi.current_dir, ".minecraft")

        print(os.listdir(wfi.minecraft_dir))

        if wfi.needs_update:
            wfi.log.info("Copying MMC json file...")

            with open(join(wfi.minecraft_dir, "mmc-pack.json")) as f, open(join(wfi.current_dir, "mmc-pack.json"),
                                                                           'w') as fh:
                fh.write(f.read())

            wfi.log.info("Copying config...")

            shutil.copytree(join(wfi.minecraft_dir, "config"), join(multimc_dir, "config"), dirs_exist_ok=True)

        db = wfi.DB(f"{wfi.minecraft_dir}/history.json")

        modpack_data_cache = db.all()

        for cache in modpack_data_cache:
            if str(cache['id']) == str(wfi.new_version):
                for mod in cache['data']['mod_data']['mods']:
                    if not exists(join(multimc_dir, "mods", mod['filename'])):
                        with open(join(wfi.cached_dir, "mods", mod['filename']), 'rb') as f, open(join(multimc_dir, "mods", mod['filename']), 'wb') as fh:
                            fh.write(f.read())
            else:
                for mod in cache['data']['mod_data']['mods']:
                    if not exists(join(multimc_dir, "mods", mod['filename'])):
                        wfi.log.debug(f"Removing previous version {mod['filename']}")
                        os.remove(join(multimc_dir, "mods", mod['filename']))


        # TODO: Copy MultiMC json from cache dir
        # TODO: Check for updates and delete old mod files from mods folder


