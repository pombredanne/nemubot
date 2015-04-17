# coding=utf-8

"""The mapquest module"""

import re
from urllib.parse import quote

from nemubot import context
from nemubot.exception import IRCException
from nemubot.tools import web

nemubotversion = 3.4

from more import Response


def load(context):
    if not context.config or not context.config.hasNode("mapquestapi") or not context.config.getNode("mapquestapi").hasAttribute("key"):
        print ("You need a MapQuest API key in order to use this "
               "module. Add it to the module configuration file:\n<mapquestapi"
               " key=\"XXXXXXXXXXXXXXXX\" />\nRegister at "
               "http://developer.mapquest.com/")
        return None

    import nemubot.hooks
    context.add_hook("cmd_hook",
                     nemubot.hooks.Message(cmd_geocode, "geocode"))


def help_full():
    return "!geocode /place/: get coordinate of /place/."


def geocode(location):
    obj = web.getJSON("http://open.mapquestapi.com/geocoding/v1/address?key=%s&location=%s" %
                      (context.config.getNode("mapquestapi")["key"], quote(location)))

    if "results" in obj and "locations" in obj["results"][0]:
        for loc in obj["results"][0]["locations"]:
            yield loc


def where(loc):
    return re.sub(" +", " ",
                  "{street} {adminArea5} {adminArea4} {adminArea3} "
                  "{adminArea1}".format(**loc)).strip()


def cmd_geocode(msg):
    if len(msg.cmds) < 2:
        raise IRCException("indicate a name")

    locname = ' '.join(msg.cmds[1:])
    res = Response(channel=msg.channel, nick=msg.nick,
                   nomore="No more geocode", count=" (%s more geocode)")

    for loc in geocode(locname):
        res.append_message("%s is at %s,%s (%s precision)" %
                           (where(loc),
                            loc["latLng"]["lat"],
                            loc["latLng"]["lng"],
                            loc["geocodeQuality"].lower()))

    return res
