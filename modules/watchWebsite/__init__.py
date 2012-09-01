# coding=utf-8

from datetime import datetime
from datetime import timedelta
import http.client
import hashlib
import re
import socket
import sys
import traceback
from urllib.parse import unquote

from .atom import Atom

nemubotversion = 3.2

def help_tiny ():
  """Line inserted in the response to the command !help"""
  return "Alert on changes on websites"

def help_full ():
  return "This module is autonomous you can't interract with it."

CONTEXT = None

def load(context):
    """Register watched website"""
    global CONTEXT
    CONTEXT = context
    for site in DATAS.getNodes("watch"):
        start_watching(site)

def unload(context):
    """Unregister watched website"""
    for site in DATAS.getNodes("watch"):
        context.del_event(site["evt_id"])

def start_watching(site):
    print_debug("Add event for site: http://%s%s" % (site["server"], site["page"]))
    evt = ModuleEvent(func=getPage, cmp_data=site["lastcontent"],
                      func_data=dict(s=site["server"], p=site["page"]),
                      intervalle=site.getInt("time"),
                      call=alert_change, call_data=site)
    site["evt_id"] = CONTEXT.add_event(evt)


def explore_url(url):
    return re.match("^(http://)?([^/]+)(/.*)$", url)

def found_site(s, p):
    for site in DATAS:
        if site["server"] == s and site["page"] == p:
            return site
    return None

def del_site(msg):
    if len(msg.cmd) <= 1:
        return Response(msg.sender, "quel site dois-je arrêter de surveiller ?",
                        msg.channel, msg.nick)

    rx = explore_url(msg.cmd[1])
    if rx is not None:
        site = found_site(rx.group(2), rx.group(3))
        if site is not None and (msg.sender == site["sender"] or msg.is_owner):
            CONTEXT.del_event(site["evt_id"])
            DATAS.delChild(site)
            return Response(msg.sender, "je ne surveille désormais plus cette URL.",
                            channel=msg.channel, nick=msg.nick)
    return Response(msg.sender, "je ne surveillais pas cette URL pour vous.",
                    channel=msg.channel, nick=msg.nick)

def add_site(msg):
    if len(msg.cmd) <= 1:
        return Response(msg.sender, "quel site dois-je surveiller ?",
                        msg.channel, msg.nick)

    rx = explore_url(msg.cmd[1])
    if rx is None:
        return Response(msg.sender, "je ne peux pas surveiller cette URL",
                        channel=msg.channel, nick=msg.nick)
    else:
        watch = ModuleState("watch")
        watch["sender"] = msg.sender
        watch["irc"] = msg.srv.id
        watch["channel"] = msg.channel
        watch["type"] = "diff"
        watch["server"] = rx.group(2)
        watch["page"] = rx.group(3)
        watch["time"] = 123
        watch["message"] = "http://%s%s a changé !" % (watch["server"],
                                                       watch["page"])
        DATAS.addChild(watch)
        start_watching(watch)

    save()
    return Response(msg.sender, channel=msg.channel, nick=msg.nick
                    message="ce site est maintenant sous ma surveillance.")

def alert_change(content, site):
    """Alert when a change is detected"""
    start_watching(site)
    if content is None:
        return

    if site["type"] == "atom":
        if site["_lastpage"] is None:
            site["_lastpage"] = Atom(site["lastcontent"])
        page = Atom(content)
        diff = site["_lastpage"].diff(page)
        if len(diff) > 0:
            site["_lastpage"] = page
            print_debug("[%s] Page differ!" % site["server"])
            diff.reverse()
            for d in diff:
                categories = site.getNodes("categories")
                categories.setIndex("term")

                if site["message"].count("%s") == 2 and len(categories) > 0:
                    if d.category is None or d.category not in categories:
                        messageI = site["message"] % (categories[""], "%s")
                    else:
                        messageI = site["message"] % (categories[d.category], "%s")
                    send_response(site["irc"], Response(site["sender"],
                                                        messageI % d.link,
                                                        site["channel"]))
                elif site["message"].count("%s") == 2:
                    send_response(site["irc"], Response(site["sender"],
                                                        site["message"] % (unquote(d.title), d.link),
                                                        site["channel"]))
                elif site["message"].count("%s") == 1:
                    send_response(site["irc"], Response(site["sender"],
                                                        site["message"] % unquote (d.title),
                                                        site["channel"]))
                else:
                    send_response(site["irc"], Response(site["sender"],
                                                        site["message"],
                                                        site["channel"]))
        else:
            return #Stop here, no changes, so don't save

    else: # Just looking for any changes
        send_response(site["irc"], Response(site["sender"], site["message"], site["channel"]))
    site["lastcontent"] = content
    save()

#TODO: built-in this function
def getPage(s, p):
    """Return the page content"""
    print_debug("Looking http://%s%s"%(s,p))
    conn = http.client.HTTPConnection(s, timeout=10)
    try:
        conn.request("GET", p)

        res = conn.getresponse()
        data = res.read()
    except:
        print ("[%s] impossible de récupérer la page %s."%(s, p))
        return None

    conn.close()
    return data.decode()
