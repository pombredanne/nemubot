# coding=utf-8

from datetime import datetime
from datetime import timedelta
import http.client
import hashlib
import re
import socket
import sys
import urllib.parse
from urllib.parse import urlparse
from urllib.request import urlopen

from hooks import hook

from .atom import Atom

nemubotversion = 3.3

def help_tiny ():
  """Line inserted in the response to the command !help"""
  return "Alert on changes on websites"

def help_full ():
  return "This module is autonomous you can't interract with it."

def load(context):
    """Register watched website"""
    DATAS.setIndex("url", "watch")
    for site in DATAS.getNodes("watch"):
        if site.hasNode("alert"):
            start_watching(site)
        else:
            print("No alert defined for this site: " + site["url"])
            #DATAS.delChild(site)

def getPageContent(url):
    """Returns the content of the given url"""
    print_debug("Get page %s" % url)
    try:
        raw = urlopen(url, timeout=10)
        return raw.read().decode()
    except:
        return None

def start_watching(site):
    o = urlparse(site["url"], "http")
    print_debug("Add event for site: %s" % o.netloc)
    evt = ModuleEvent(func=getPageContent, cmp_data=site["lastcontent"],
                      func_data=site["url"],
                      intervalle=site.getInt("time"),
                      call=alert_change, call_data=site)
    site["_evt_id"] = add_event(evt)


@hook("cmd_hook", "unwatch")
def del_site(msg):
    if len(msg.cmds) <= 1:
        raise IRCException("quel site dois-je arrêter de surveiller ?")

    url = msg.cmds[1]

    o = urlparse(url, "http")
    if o.scheme != "" and url in DATAS.index:
        site = DATAS.index[url]
        for a in site.getNodes("alert"):
            if a["channel"] == msg.channel:
                if not (msg.sender == a["sender"] or msg.is_owner):
                    raise IRCException("vous ne pouvez pas supprimer cette URL.")
                site.delChild(a)
                if not site.hasNode("alert"):
                    del_event(site["_evt_id"])
                    DATAS.delChild(site)
                save()
                return Response(msg.sender,
                                "je ne surveille désormais plus cette URL.",
                                channel=msg.channel, nick=msg.nick)
    raise IRCException("je ne surveillais pas cette URL !")


@hook("cmd_hook", "watch", data="diff")
@hook("cmd_hook", "updown", data="updown")
def add_site(msg, diffType="diff"):
    print (diffType)
    if len(msg.cmds) <= 1:
        raise IRCException("quel site dois-je surveiller ?")

    url = msg.cmds[1]

    o = urlparse(url, "http")
    if o.netloc == "":
        raise IRCException("je ne peux pas surveiller cette URL")

    alert = ModuleState("alert")
    alert["sender"] = msg.sender
    alert["server"] = msg.server
    alert["channel"] = msg.channel
    alert["message"] = "%s a changé !" % url

    if url not in DATAS.index:
        watch = ModuleState("watch")
        watch["type"] = diffType
        watch["url"] = url
        watch["time"] = 123
        DATAS.addChild(watch)
        watch.addChild(alert)
        start_watching(watch)
    else:
        DATAS.index[url].addChild(alert)

    save()
    return Response(msg.sender, channel=msg.channel, nick=msg.nick,
                    message="ce site est maintenant sous ma surveillance.")

def format_response(site, link='%s', title='%s', categ='%s'):
    for a in site.getNodes("alert"):
        send_response(a["server"], Response(a["sender"], a["message"].format(url=site["url"], link=link, title=title, categ=categ),
                                     channel=a["channel"], server=a["server"]))

def alert_change(content, site):
    """Alert when a change is detected"""
    if site["type"] == "updown":
        if site["lastcontent"] is None:
            site["lastcontent"] = content is not None

        if (content is not None) != site.getBool("lastcontent"):
            format_response(site, link=site["url"])
            site["lastcontent"] = content is not None
        start_watching(site)
        return

    if content is None:
        start_watching(site)
        return

    if site["type"] == "atom":
        if site["_lastpage"] is None:
            if site["lastcontent"] is None or site["lastcontent"] == "":
                site["lastcontent"] = content
            site["_lastpage"] = Atom(site["lastcontent"])
        try:
            page = Atom(content)
        except:
            print ("An error occurs during Atom parsing. Restart event...")
            start_watching(site)
            return
        diff = site["_lastpage"].diff(page)
        if len(diff) > 0:
            site["_lastpage"] = page
            diff.reverse()
            for d in diff:
                site.setIndex("term", "category")
                categories = site.index

                if len(categories) > 0:
                    if d.category is None or d.category not in categories:
                        format_response(site, link=d.link, categ=categories[""]["part"], title=d.title)
                    else:
                        format_response(site, link=d.link, categ=categories[d.category]["part"], title=d.title)
                else:
                    format_response(site, link=d.link, title=urllib.parse.unquote(d.title))
        else:
            start_watching(site)
            return #Stop here, no changes, so don't save

    else: # Just looking for any changes
        format_response(site, link=site["url"])
    site["lastcontent"] = content
    start_watching(site)
    save()
