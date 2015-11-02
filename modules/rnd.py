"""Help to make choice"""

# PYTHON STUFFS #######################################################

import random
import shlex

from nemubot import context
from nemubot.exception import IMException
from nemubot.hooks import hook
from nemubot.message import Command

from more import Response


# MODULE INTERFACE ####################################################

@hook.command("choice")
def cmd_choice(msg):
    if not len(msg.args):
        raise IMException("indicate some terms to pick!")

    return Response(random.choice(msg.args),
                    channel=msg.channel,
                    nick=msg.nick)


@hook.command("choicecmd")
def cmd_choicecmd(msg):
    if not len(msg.args):
        raise IMException("indicate some command to pick!")

    choice = shlex.split(random.choice(msg.args))

    return [x for x in context.subtreat(Command(choice[0][1:],
                                                choice[1:],
                                                to_response=msg.to_response,
                                                frm=msg.frm,
                                                server=msg.server))]
