# -*- coding: utf-8 -*-

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
import queue
import re
import threading
import traceback
import sys

import bot
from server.DCC import DCC
from message import Message
from response import Response
import server

logger = logging.getLogger("nemubot.consumer")

class MessageConsumer:

    """Store a message before treating"""

    def __init__(self, srv, msg):
        self.srv = srv

        self.msgs = [ msg ]
        self.responses = None


    def first_treat(self, msg):
        """Qualify a new message/response

        Argument:
        msg -- The Message or Response to qualify
        """

        if not hasattr(msg, "qual") or msg.qual is None:
            # Assume this is a message with no particulariry
            msg.qual = "def"

        # Define the source server if not already done
        if not hasattr(msg, "server") or msg.server is None:
            msg.server = self.srv.id

        if isinstance(msg, Message):
            if msg.cmd == "PRIVMSG" or msg.cmd == "NOTICE":
                msg.is_owner = (msg.nick == self.srv.owner)
                msg.private = msg.private or (len(msg.receivers) == 1 and msg.receivers[0] == self.srv.nick)
                if msg.private:
                    msg.qual = "ask"

                # Remove nemubot:
                if msg.qual != "cmd" and msg.text.find(self.srv.nick) == 0 and len(msg.text) > len(self.srv.nick) + 2 and msg.text[len(self.srv.nick)] == ":":
                    msg.text = msg.text[len(self.srv.nick) + 1:].strip()
                    msg.qual = "ask"

        return msg


    def pre_treat(self, hm):
        """Modify input Messages

        Arguments:
        hm -- Hooks manager
        """

        new_msg = list()
        new_msg += self.msgs
        self.msgs = list()

        while len(new_msg) > 0:
            msg = new_msg.pop(0)
            for h in hm.get_hooks("pre", msg.cmd, msg.qual):
                if h.match(message=msg, server=self.srv):
                    res = h.run(msg)
                    if isinstance(res, list):
                        for i in xrange(len(res)):
                            if res[i] == msg:
                                res.pop(i)
                                break
                        new_msg += res
                    elif res is not None and res != msg:
                        new_msg.append(res)
                        msg = None
                        break
                    elif res is None or res == False:
                        msg = None
                        break
            if msg is not None:
                self.msgs.append(msg)


    def in_treat(self, hm):
        """Treat Messages and store responses

        Arguments:
        hm -- Hooks manager
        """

        self.responses = list()
        for msg in self.msgs:
            for h in hm.get_hooks("in", msg.cmd, msg.qual):
                if h.match(message=msg, server=self.srv):
                    res = h.run(msg)
                    if isinstance(res, list):
                        for r in res:
                            if isinstance(r, Response):
                                r.set_sender(msg.sender)
                        self.responses += res
                    elif res is not None:
                        if isinstance(res, Response):
                            res.set_sender(msg.sender)
                        self.responses.append(res)


    def post_treat(self, hm):
        """Modify output Messages

        Arguments:
        hm -- Hooks manager
        """

        new_msg = list()
        new_msg += self.responses
        self.responses = list()

        while len(new_msg) > 0:
            msg = self.first_treat(new_msg.pop(0))
            for h in hm.get_hooks("post"):
                if h.match(message=msg, server=self.srv):
                    res = h.run(msg)
                    if isinstance(res, list):
                        for i in xrange(len(res)):
                            if res[i] == msg:
                                res.pop(i)
                                break
                        new_msg += res
                    elif res is not None and res != msg:
                        new_msg.append(res)
                        msg = None
                        break
                    elif res is None or res == False:
                        msg = None
                        break
            if msg is not None:
                self.responses.append(msg)


    def run(self, context):
        """Create, parse and treat the message"""
        try:
            for msg in self.msgs:
                self.first_treat(msg)

            # Run pre-treatment: from Message to [ Message ]
            self.pre_treat(context.hooks)

            # Run in-treatment: from Message to [ Response ]
            if len(self.msgs) > 0:
                self.in_treat(context.hooks)

            # Run post-treatment: from Response to [ Response ]
            if self.responses is not None and len(self.responses) > 0:
                self.post_treat(context.hooks)
        except:
            logger.exception("Error occurred during the processing of the message: %s", self.msgs[0].raw)

        for res in self.responses:
            to_server = None
            if res.server is None:
                to_server = self.srv
                res.server = self.srv.id
            elif isinstance(res.server, str) and res.server in context.servers:
                to_server = context.servers[res.server]

            if to_server is None:
                logger.error("The server defined in this response doesn't "
                             "exist: %s", res.server)
                continue

            # Sent the message only if treat_post authorize it
            to_server.send_response(res)

class EventConsumer:
    """Store a event before treating"""
    def __init__(self, evt, timeout=20):
        self.evt = evt
        self.timeout = timeout


    def run(self, context):
        try:
            self.evt.check()
        except:
            logger.exception("Error during event end")

        # Reappend the event in the queue if it has next iteration
        if self.evt.next is not None:
            context.add_event(self.evt, eid=self.evt.id)

        # Or remove reference of this event
        elif hasattr(self.evt, "module_src") and self.evt.module_src is not None:
            self.evt.module_src.REGISTERED_EVENTS.remove(self.evt.id)



class Consumer(threading.Thread):
    """Dequeue and exec requested action"""
    def __init__(self, context):
        self.context = context
        self.stop = False
        threading.Thread.__init__(self)

    def run(self):
        try:
            while not self.stop:
                stm = self.context.cnsr_queue.get(True, 20)
                stm.run(self.context)
                self.context.cnsr_queue.task_done()

        except queue.Empty:
            pass
        finally:
            self.context.cnsr_thrd_size -= 2
            self.context.cnsr_thrd.remove(self)
