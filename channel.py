# coding=utf-8

# Nemubot is a modulable IRC bot, built around XML configuration files.
# Copyright (C) 2012  Mercier Pierre-Olivier
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

import logging

class Channel:
    def __init__(self, name, password=None):
        self.name = name
        self.password = password
        self.people = dict()
        self.topic = ""
        self.logger = logging.getLogger("nemubot.channel." + name)

    def treat(self, cmd, msg):
        if cmd == "353":
            self.parse353(msg)
        elif cmd == "332":
            self.parse332(msg)
        elif cmd == "MODE":
            self.mode(msg)
        elif cmd == "JOIN":
            self.join(msg.nick)
        elif cmd == "NICK":
            self.nick(msg.nick, msg.text)
        elif cmd == "PART" or cmd == "QUIT":
            self.part(msg.nick)
        elif cmd == "TOPIC":
            self.topic = self.text

    def join(self, nick, level = 0):
        """Someone join the channel"""
        self.logger.debug("%s join", nick)
        self.people[nick] = level

    def chtopic(self, newtopic):
        """Send command to change the topic"""
        self.srv.send_msg(self.name, newtopic, "TOPIC")
        self.topic = newtopic

    def nick(self, oldnick, newnick):
        """Someone change his nick"""
        if oldnick in self.people:
            self.logger.debug("%s switch nick to %s on", oldnick, newnick)
            lvl = self.people[oldnick]
            del self.people[oldnick]
            self.people[newnick] = lvl

    def part(self, nick):
        """Someone leave the channel"""
        if nick in self.people:
            self.logger.debug("%s has left", nick)
            del self.people[nick]

    def mode(self, msg):
        if msg.text[0] == "-k":
            self.password = ""
        elif msg.text[0] == "+k":
            if len(msg.text) > 1:
                self.password = ' '.join(msg.text[1:])[1:]
            else:
                self.password = msg.text[1]
        elif msg.text[0] == "+o":
            self.people[msg.nick] |= 4
        elif msg.text[0] == "-o":
            self.people[msg.nick] &= ~4
        elif msg.text[0] == "+h":
            self.people[msg.nick] |= 2
        elif msg.text[0] == "-h":
            self.people[msg.nick] &= ~2
        elif msg.text[0] == "+v":
            self.people[msg.nick] |= 1
        elif msg.text[0] == "-v":
            self.people[msg.nick] &= ~1

    def parse332(self, msg):
        self.topic = msg.text

    def parse353(self, msg):
        for p in msg.text:
            p = p.decode()
            if p[0] == "@":
                level = 4
            elif p[0] == "%":
                level = 2
            elif p[0] == "+":
                level = 1
            else:
                self.join(p, 0)
                continue
            self.join(p[1:], level)
