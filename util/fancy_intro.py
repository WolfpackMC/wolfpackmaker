
from platform import version

import owoify
from pyfiglet import Figlet


def fancy_intro(log, with_figlet=True, description=''):
    f = Figlet()
    chars = with_figlet and '####' or '#'
    char_range = with_figlet and 16 or 43
    log.info(str('').join([chars for _ in range(char_range)]))
    log.info(with_figlet and f.renderText("wolfpackmaker") or description)
    import random
    keywords = random.choice(
        ['A custom made Minecraft modpack script. Nothing special, hehe.',
         'Please don\'t tell anyone about this...',
         'Hehe. UwU, It\'s all we have, I know. I\'m sorry!'
         ]
    )
    log.info(owoify.owoify(keywords))
    log.info(str('').join([chars for _ in range(char_range)]))
