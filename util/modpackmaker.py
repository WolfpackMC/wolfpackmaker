import requests

from rich import inspect

import time

game_version = ['1.12.2']

def main():
    test = requests.get("https://get.kalka.io/curseforge.json")
    data = test.json()
    filtered_data = [d for d in data for f in d['latest_files'] if f['gameVersion'] in game_version][:500]
    string_aggregate = str()
    mods = []
    for d in filtered_data:
        if d['name'] in mods:
            continue
        mods.append(d['name'])
        string_aggregate += f'- {d["slug"]}:\n'
    with open(f'mods-{int(time.time())}.yml', 'w') as f:
        f.write(string_aggregate)
    print("Done.")


main()
