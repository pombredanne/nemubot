# Nemubot is a smart and modulable IM bot.
# Copyright (C) 2012-2016  Mercier Pierre-Olivier
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


def factory(uri, ssl=False, **init_args):
    from urllib.parse import urlparse, unquote
    o = urlparse(uri)

    srv = None

    if o.scheme == "irc" or o.scheme == "ircs":
        # http://www.w3.org/Addressing/draft-mirashi-url-irc-01.txt
        # http://www-archive.mozilla.org/projects/rt-messaging/chatzilla/irc-urls.html
        args = init_args

        if o.scheme == "ircs": ssl = True
        if o.hostname is not None: args["host"] = o.hostname
        if o.port is not None: args["port"] = o.port
        if o.username is not None: args["username"] = o.username
        if o.password is not None: args["password"] = o.password

        if ssl:
            try:
                from ssl import create_default_context
                args["_context"] = create_default_context()
            except ImportError:
                # Python 3.3 compat
                from ssl import SSLContext, PROTOCOL_TLSv1
                args["_context"] = SSLContext(PROTOCOL_TLSv1)
            args["server_hostname"] = o.hostname

        modifiers = o.path.split(",")
        target = unquote(modifiers.pop(0)[1:])

        queries = o.query.split("&")
        for q in queries:
            if "=" in q:
                key, val = tuple(q.split("=", 1))
            else:
                key, val = q, ""
            if key == "msg":
                if "on_connect" not in args:
                    args["on_connect"] = []
                args["on_connect"].append("PRIVMSG %s :%s" % (target, unquote(val)))
            elif key == "key":
                if "channels" not in args:
                    args["channels"] = []
                args["channels"].append((target, unquote(val)))
            elif key == "pass":
                args["password"] = unquote(val)
            elif key == "charset":
                args["encoding"] = unquote(val)

        if "channels" not in args and "isnick" not in modifiers:
            args["channels"] = [ target ]

        if ssl:
            from nemubot.server.IRC import IRC_secure as SecureIRCServer
            srv = SecureIRCServer(**args)
        else:
            from nemubot.server.IRC import IRC as IRCServer
            srv = IRCServer(**args)

    return srv
