
from platform import version

import owoify
from pyfiglet import Figlet


def fancy_intro(log):
    f = Figlet()
    log.info(str('').join(['####' for _ in range(16)]))
    log.info(f.renderText(("wolfpackmaker")))
    import random
    keywords = random.choice(
        ['A custom made Minecraft modpack script. Nothing special, hehe.',
         'Please don\'t tell anyone about this...',
         'Hehe. UwU, It\'s all we have, I know. I\'m sorry!',
         'I should probably get a better idea for this list...',
         'Not sponsored by Awoos!'
         ]
    )
    log.info(owoify.owoify(keywords))
    log.info(str('').join(['####' for _ in range(16)]))
