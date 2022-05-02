import io
import shutil
from os import getcwd, remove
from os.path import dirname, join, exists
from pathlib import Path
from zipfile import ZipFile

from appdirs import user_cache_dir
from pkg_resources import get_distribution
from rich.progress import TextColumn, TransferSpeedColumn, DownloadColumn, BarColumn, TimeRemainingColumn, Progress
from rich.table import Column
from wolfpackmaker.launchers.multimc import MultiMC

from wolfpackutil import WolfpackUtil


class WolfpackMaker(WolfpackUtil):
    launchers = [
        "multimc"
    ]

    def __init__(self):
        super().__init__()
        self.__version__ = get_distribution('wolfpackmaker').version

        self.info = f"Wolfpackmaker {self.__version__}".split()
        self.name = self.info[0].lower()
        self.version = self.info[1]
        self.parser = self.init_args()
        self.args = self.parser.parse_args()
        self.log.parse_log(self.args)
        self.log.fancy_intro(self.name, version=self.version)
        self.repo_info = {
            "user": self.author,
            "repo": self.args.repo,
            "github_files": ['manifest.lock', 'config.zip']
        }

        self.modpack_name = self.args.repo.lower()

        self.headers = {
            'Authorization': 'token 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',
            'User-Agent': f'{self.name} {self.version}'
        }

        self.current_dir = self.args.dir and self.args.dir or getcwd()
        self.parent_dir = dirname(self.current_dir)
        self.cached_dir = user_cache_dir(self.name)

        self.modpacks_dir = join(self.cached_dir, 'modpacks')

        self.minecraft_dir = join(self.modpacks_dir, self.modpack_name)

        self.resourcepack_dir = join(self.minecraft_dir, 'resourcepacks')

        self.config_dir = join(self.minecraft_dir, 'config')

        self.mods_dir = \
            self.args.download and join(self.current_dir, self.args.download) or join(self.minecraft_dir, "mods")

        self.mods_cache_dir = \
            self.args.cache and join(self.current_dir, self.args.cache) or join(self.cached_dir, "mods")

        self.version = None
        self.new_version = None
        self.needs_update = True

    def main(self):
        self.create_folders()
        with self.Session() as session:
            session.headers.update(self.headers)
            self.log.info("Getting GitHub data...")
            github_data = session.get(self.github_url.format(self.repo_info['user'], self.repo_info['repo']))
            self.needs_update = True

            if exists(f'{self.minecraft_dir}/VERSION'):
                with open(f'{self.minecraft_dir}/VERSION') as fh:
                    self.version = fh.read()

            modpack_data = github_data.json()[0]
            self.new_version = str(modpack_data['id'])

            if self.version == str(modpack_data['id']):
                self.log.info("Modpack is already up to date.")
                self.needs_update = False

            mod_data = {}

            for asset in modpack_data['assets']:
                if asset['name'] in self.repo_info['github_files']:
                    mod_data[asset['name']] = asset['browser_download_url']

            mod_data['manifest.lock'] = session.get(mod_data['manifest.lock']).json()

            if self.needs_update:
                mod_data['config.zip'] = session.get(mod_data['config.zip']).content
                self.log.debug("Converting config.zip to BytesIO...")
                mod_data['config.zip'] = io.BytesIO(mod_data['config.zip'])
                self.log.debug("Converting to zip...")
                mod_data['config.zip'] = ZipFile(mod_data['config.zip'])
                self.log.info("Extracting modpack config...")
                mod_data['config.zip'].extractall(self.minecraft_dir)
                mod_data['config.zip'] = None

                if exists(join(self.minecraft_dir, ".minecraft")):
                    shutil.copytree(join(self.minecraft_dir, ".minecraft"), join(self.minecraft_dir, "config"),
                                    dirs_exist_ok=True)
                    shutil.rmtree(join(self.minecraft_dir, ".minecraft"))

                configignore_dir = join(self.minecraft_dir, "config", "config", ".configignore")

                if exists(configignore_dir):
                    with open(configignore_dir) as fh:
                        for line in fh.read().splitlines():
                            if exists(join(configignore_dir, line)):
                                self.log.info(f"Ignoring {line}...")
                                remove(join(configignore_dir, line))

            filesize = 0

            to_download = []

            with Progress(refresh_per_second=60, expand=True) as p:
                task = p.add_task(description="\t\tVerifying mods...", total=len(mod_data['manifest.lock']['mods']))
                for mod in mod_data['manifest.lock']['mods']:
                    if exists(join(self.cached_dir, "mods", mod['filename'])):
                        try:
                            with open(join(self.cached_dir, "mods", mod['filename']), 'rb') as fh:
                                local_length = len(fh.read())
                                verified = local_length == mod['fileLength']
                        except FileNotFoundError:
                            verified = False

                        if not verified:
                            print("\t" +
                                  f"{mod['name']} requires a re-download. "
                                  f"{local_length} / {mod['fileLength']} byte mismatch")
                            to_download.append(mod)
                    else:
                        to_download.append(mod)

                    p.advance(task)

                if not exists(join(self.cached_dir, "mods", mod['filename'])):
                    filesize += mod['fileLength']

            sorted_mods = reversed(sorted(to_download, key=lambda x: x['fileLength']))

            for mod in sorted_mods:
                with Progress(
                        TextColumn("\t> [yellow][progress.description]{task.description}",
                                   table_column=Column(ratio=4)),
                        TransferSpeedColumn(table_column=Column(ratio=4)),
                        DownloadColumn(table_column=Column(ratio=2)),
                        BarColumn(bar_width=None, table_column=Column(ratio=2)),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        TimeRemainingColumn(),
                        refresh_per_second=60,
                        expand=True
                ) as p:
                    task = p.add_task(description=mod['name'], total=int(mod['fileLength']))
                    mod_r = session.get(mod['downloadUrl'], stream=True)

                    with open(join(self.cached_dir, "mods", mod['filename']), 'wb') as fh:
                        for chunk in mod_r.iter_content(65535):
                            fh.write(chunk)
                            p.advance(task, len(chunk))

                    p.update(task, description=f"[green]{mod['name']}")

        with open(f'{self.minecraft_dir}/VERSION', 'w') as fh:
            fh.write(self.new_version)

        db = self.DB(f"{self.minecraft_dir}/history.json")

        if not db.contains(db.q.id == modpack_data['id']):
            db.insert({"id": modpack_data['id'],
                       "data": {"github_data": modpack_data, "mod_data": mod_data['manifest.lock']}})

        if self.args.launcher is None:
            self.log.warn(f"Please choose a launcher. Available launchers: {[launcher for launcher in self.launchers]}")
            return

        if self.args.launcher not in self.launchers:
            self.log.warn(
                f"{self.args.launcher} is not supported at this time. Available launchers: {[launcher for launcher in self.launchers]}")
            return

        if self.args.launcher == 'multimc':
            self.log.info("Assembling modpack with MultiMC...")
            MultiMC(self)

    def init_args(self):
        parser = self.Parser(description=f"{self.name} {self.version}", prog=f"{self.name}")
        parser.add_argument('-v', '--verbose', help='Increase output verbosity.', action='store_true')
        parser.add_argument('-r', '--repo', help="Wolfpack modpack repository.", required=True)
        parser.add_argument('--dir', help=f'Custom directory for Wolfpackmaker. Defaults to {dirname(getcwd())}')
        parser.add_argument('-mcdir', '--minecraft-dir', help='Specify custom minecraft dir. Defaults to .minecraft',
                            default='.minecraft')
        parser.add_argument('-l', '--launcher',
                            help=f"Specify the launcher. Available launchers: {[launcher for launcher in self.launchers]}")
        parser.add_argument('-d', '--download', help='Custom download directory')
        parser.add_argument('--cache', help='Custom cache directory')
        return parser

    def create_folders(self):
        Path(self.cached_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.cached_dir}")
        Path(self.minecraft_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.minecraft_dir}")
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.config_dir}")
        Path(self.mods_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.mods_dir}")
        Path(self.resourcepack_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.resourcepack_dir}")
        Path(self.mods_cache_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.mods_cache_dir}")
        Path(join(self.cached_dir, 'cached_config')).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {join(self.cached_dir, 'cached_config')}")
        Path(self.modpacks_dir).mkdir(parents=True, exist_ok=True)
        self.log.debug(f"Successfully created directory {self.modpacks_dir}")
