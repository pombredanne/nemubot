# coding=utf-8

"""Various network tools (w3m, w3c validator, curl, traceurl, ...)"""

from hooks import hook

nemubotversion = 3.4

from more import Response

from . import isup
from . import page
from . import w3c
from . import watchWebsite
from . import whois

def load(context):
    for mod in [isup, page, w3c, watchWebsite, whois]:
        mod.IRCException = IRCException
        mod.ModuleEvent = ModuleEvent
        mod.add_event = add_event
        mod.save = save
        mod.print = print
        mod.print_debug = print_debug
        mod.send_response = send_response
    page.load(CONF, add_hook)
    watchWebsite.load(DATAS)
    whois.load(CONF, add_hook)


def help_full():
    return "!traceurl /url/: Follow redirections from /url/."


@hook("cmd_hook", "curly")
def cmd_curly(msg):
    if len(msg.cmds) < 2:
        raise IRCException("Indicate the URL to visit.")

    url = " ".join(msg.cmds[1:])
    version, status, reason, headers = page.headers(url)

    return Response("Entêtes de la page %s : HTTP/%s, statut : %d %s ; headers : %s" % (url, version, status, reason, ", ".join(["\x03\x02" + h + "\x03\x02: " + v for h, v in headers])), channel=msg.channel)


@hook("cmd_hook", "curl")
def cmd_curl(msg):
    if len(msg.cmds) < 2:
        raise IRCException("Indicate the URL to visit.")

    res = Response(channel=msg.channel)
    for m in page.fetch(" ".join(msg.cmds[1:])).split("\n"):
        res.append_message(m)
    return res


@hook("cmd_hook", "w3m")
def cmd_w3m(msg):
    if len(msg.cmds) > 1:
        res = Response(channel=msg.channel)
        for line in page.render(" ".join(msg.cmds[1:])).split("\n"):
            res.append_message(line)
        return res
    else:
        raise IRCException("Indicate the URL to visit.")


@hook("cmd_hook", "traceurl")
def cmd_traceurl(msg):
    if 1 < len(msg.cmds) < 6:
        res = list()
        for url in msg.cmds[1:]:
            trace = page.traceURL(url)
            res.append(Response(trace, channel=msg.channel, title="TraceURL"))
        return res
    else:
        raise IRCException("Indicate an URL to trace!")


@hook("cmd_hook", "isup")
def cmd_isup(msg):
    if 1 < len(msg.cmds) < 6:
        res = list()
        for url in msg.cmds[1:]:
            rep = isup.isup(url)
            if rep:
                res.append(Response("%s is up (response time: %ss)" % (url, rep), channel=msg.channel))
            else:
                res.append(Response("%s is down" % (url), channel=msg.channel))
        return res
    else:
        return Response("Indicate an URL to check!", channel=msg.channel)


@hook("cmd_hook", "w3c")
def cmd_w3c(msg):
    if len(msg.cmds) < 2:
        raise IRCException("Indicate an URL to validate!")

    headers, validator = w3c.validator(msg.cmds[1])

    res = Response(channel=msg.channel, nomore="No more error")

    res.append_message("%s: status: %s, %s warning(s), %s error(s)" % (validator["url"], headers["X-W3C-Validator-Status"], headers["X-W3C-Validator-Warnings"], headers["X-W3C-Validator-Errors"]))

    for m in validator["messages"]:
        if "lastLine" not in m:
            res.append_message("%s%s: %s" % (m["type"][0].upper(), m["type"][1:], m["message"]))
        else:
            res.append_message("%s%s on line %s, col %s: %s" % (m["type"][0].upper(), m["type"][1:], m["lastLine"], m["lastColumn"], m["message"]))

    return res



@hook("cmd_hook", "watch", data="diff")
@hook("cmd_hook", "updown", data="updown")
def cmd_watch(msg, diffType="diff"):
    if len(msg.cmds) <= 1:
        raise IRCException("indicate an URL to watch!")

    return watchWebsite.add_site(msg.cmds[1])


@hook("cmd_hook", "unwatch")
def cmd_unwatch(msg):
    if len(msg.cmds) <= 1:
        raise IRCException("which URL should I stop watching?")

    return watchWebsite.add_site(msg.cmds[1])
