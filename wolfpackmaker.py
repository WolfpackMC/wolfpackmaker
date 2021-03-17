import json
import logging
import coloredlogs
import os
import sys

from zipfile import ZipFile
from datetime import datetime

import urllib3
from packmaker.main import main as packmaker_main


def logger_install():
    platform = sys.platform
    if platform == 'linux' or platform == 'linux2' or platform == 'darwin':
        coloredlogs.install(
            format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(
            format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S')


logger_install()


user = "Wolfpack"
repo = sys.argv[1] or ""  # format: https://git.kalka.io/kalka/gilneas
gitea_api = "https://git.kalka.io/api/v1/repos/{}/{}/releases"


def get_http_data(url, method='GET'):
    http = urllib3.PoolManager()  # create our own instance
    logging.debug("Initialized our http pool manager")
    r = http.request(method, url)
    data = r.data
    logging.debug(r.status)
    http.clear()  # close the pool connection
    return data


def parse_data(data):
    return json.loads(data)


def write_data(file, data):
    f = open(file, 'wb')
    logging.debug("Successfully opened a connection with " + file)
    f.write(data)
    logging.debug("Wrote the data to " + file)
    f.close()


def unzip_data(file, location):
    zf = ZipFile(file)
    logging.debug("Extracting " + file + "...")
    zf.extractall(location)
    logging.debug("Complete.")
    zf.close()


def get_urls(url):
    data = parse_data(get_http_data(url))
    manifest = {
        "lock": data[0]['assets'][2]["browser_download_url"],
        "config": data[0]['assets'][1]["browser_download_url"],
        "time": data[0]['created_at']
    }
    lock = manifest.get("lock")
    config = manifest.get("config")
    time = datetime.strptime(manifest.get("time"), '%Y-%m-%dT%H:%M:%S%z')
    logging.info("Both URLs returned: " + lock + " and " + config)
    logging.info("The time we have for the config file is: {}".format(time))
    return lock, config, time


def write_config(config):
    write_data('config.zip', get_http_data(config))
    unzip_data('config.zip', '../')


def main():
    lock, config, time = get_urls(gitea_api.format(user, repo))
    write_data('packmaker.lock', get_http_data(lock))
    if os.path.exists('config.zip'):
        if (time.timestamp() > os.path.getmtime('config.zip')):
            logging.info("Config requires update!")
            write_config(config)
        else:
            logging.info("We need not an update.")
    else:
        logging.info("A config zip has not been found. Bazinga!")
        write_config(config)
    logging.info("All done here. Back to you, packmaker.")

    packmaker_main(args=sys.argv[2:])


main()
