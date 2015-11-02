# Nemubot is a smart and modulable IM bot.
# Copyright (C) 2012-2015  Mercier Pierre-Olivier
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

from datetime import datetime, timezone
import logging
import threading
import sys

from nemubot import __version__
from nemubot.consumer import Consumer, EventConsumer, MessageConsumer
from nemubot import datastore
import nemubot.hooks

logger = logging.getLogger("nemubot")


class Bot(threading.Thread):

    """Class containing the bot context and ensuring key goals"""

    def __init__(self, ip="127.0.0.1", modules_paths=list(),
                 data_store=datastore.Abstract(), verbosity=0):
        """Initialize the bot context

        Keyword arguments:
        ip -- The external IP of the bot (default: 127.0.0.1)
        modules_paths -- Paths to all directories where looking for module
        data_store -- An instance of the nemubot datastore for bot's modules
        """

        threading.Thread.__init__(self)

        logger.info("Initiate nemubot v%s", __version__)

        self.verbosity = verbosity
        self.stop = None

        # External IP for accessing this bot
        import ipaddress
        self.ip = ipaddress.ip_address(ip)

        # Context paths
        self.modules_paths = modules_paths
        self.datastore = data_store
        self.datastore.open()

        # Keep global context: servers and modules
        self.servers = dict()
        self.modules = dict()
        self.modules_configuration = dict()

        # Events
        self.events      = list()
        self.event_timer = None

        # Own hooks
        from nemubot.treatment import MessageTreater
        self.treater     = MessageTreater()

        import re
        def in_ping(msg):
            if re.match("^ *(m[' ]?entends?[ -]+tu|h?ear me|do you copy|ping)", msg.message, re.I) is not None:
                return msg.respond("pong")
        self.treater.hm.add_hook(nemubot.hooks.Message(in_ping), "in", "DirectAsk")

        def in_echo(msg):
            from nemubot.message import Text
            return Text(msg.nick + ": " + " ".join(msg.args), to=msg.to_response)
        self.treater.hm.add_hook(nemubot.hooks.Command(in_echo, "echo"), "in", "Command")

        def _help_msg(msg):
            """Parse and response to help messages"""
            from more import Response
            res = Response(channel=msg.to_response)
            if len(msg.args) >= 1:
                if msg.args[0] in self.modules:
                    if hasattr(self.modules[msg.args[0]], "help_full"):
                        hlp = self.modules[msg.args[0]].help_full()
                        if isinstance(hlp, Response):
                            return hlp
                        else:
                            res.append_message(hlp)
                    else:
                        res.append_message([str(h) for s,h in self.modules[msg.args[0]].__nemubot_context__.hooks], title="Available commands for module " + msg.args[0])
                elif msg.args[0][0] == "!":
                    for module in self.modules:
                        for (s, h) in self.modules[module].__nemubot_context__.hooks:
                            if s == "in_Command" and (h.name is not None or h.regexp is not None) and ((h.name is not None and msg.args[0][1:] == h.name) or (h.regexp is not None and re.match(h.regexp, msg.args[0][1:]))):
                                if h.help_usage:
                                    lp = ["\x03\x02%s%s\x03\x02: %s" % (msg.args[0], (" " + k if k is not None else ""), h.help_usage[k]) for k in h.help_usage]
                                    jp = h.keywords.help()
                                    return res.append_message(lp + ([". Moreover, you can provides some optional parameters: "] + jp if len(jp) else []), title="Usage for command %s from module %s" % (msg.args[0], module))
                                elif h.help:
                                    return res.append_message("Command %s from module %s: %s" % (msg.args[0], module, h.help))
                                else:
                                    return res.append_message("Sorry, there is currently no help for the command %s. Feel free to make a pull request at https://github.com/nemunaire/nemubot/compare" % msg.args[0])
                    else:
                        res.append_message("Sorry, there is no command %s" % msg.args[0])
                else:
                    res.append_message("Sorry, there is no module named %s" % msg.args[0])
            else:
                res.append_message("Pour me demander quelque chose, commencez "
                                   "votre message par mon nom ; je réagis "
                                   "également à certaine commandes commençant par"
                                   " !.  Pour plus d'informations, envoyez le "
                                   "message \"!more\".")
                res.append_message("Mon code source est libre, publié sous "
                                   "licence AGPL (http://www.gnu.org/licenses/). "
                                   "Vous pouvez le consulter, le dupliquer, "
                                   "envoyer des rapports de bogues ou bien "
                                   "contribuer au projet sur GitHub : "
                                   "http://github.com/nemunaire/nemubot/")
                res.append_message(title="Pour plus de détails sur un module, "
                                   "envoyez \"!help nomdumodule\". Voici la liste"
                                   " de tous les modules disponibles localement",
                                   message=["\x03\x02%s\x03\x02 (%s)" % (im, self.modules[im].__doc__) for im in self.modules if self.modules[im].__doc__])
            return res
        self.treater.hm.add_hook(nemubot.hooks.Command(_help_msg, "help"), "in", "Command")

        from queue import Queue
        # Messages to be treated
        self.cnsr_queue     = Queue()
        self.cnsr_thrd      = list()
        self.cnsr_thrd_size = -1
        # Synchrone actions to be treated by main thread
        self.sync_queue     = Queue()


    def run(self):
        from select import select
        from nemubot.server import _lock, _rlist, _wlist, _xlist

        self.stop = False
        while not self.stop:
            with _lock:
                try:
                    rl, wl, xl = select(_rlist, _wlist, _xlist, 0.1)
                except:
                    logger.error("Something went wrong in select")
                    fnd_smth = False
                    # Looking for invalid server
                    for r in _rlist:
                        if not hasattr(r, "fileno") or not isinstance(r.fileno(), int) or r.fileno() < 0:
                            _rlist.remove(r)
                            logger.error("Found invalid object in _rlist: " + str(r))
                            fnd_smth = True
                    for w in _wlist:
                        if not hasattr(w, "fileno") or not isinstance(w.fileno(), int) or w.fileno() < 0:
                            _wlist.remove(w)
                            logger.error("Found invalid object in _wlist: " + str(w))
                            fnd_smth = True
                    for x in _xlist:
                        if not hasattr(x, "fileno") or not isinstance(x.fileno(), int) or x.fileno() < 0:
                            _xlist.remove(x)
                            logger.error("Found invalid object in _xlist: " + str(x))
                            fnd_smth = True
                    if not fnd_smth:
                        logger.exception("Can't continue, sorry")
                        self.quit()
                    continue

                for x in xl:
                    try:
                        x.exception()
                    except:
                        logger.exception("Uncatched exception on server exception")
                for w in wl:
                    try:
                        w.write_select()
                    except:
                        logger.exception("Uncatched exception on server write")
                for r in rl:
                    for i in r.read():
                        try:
                            self.receive_message(r, i)
                        except:
                            logger.exception("Uncatched exception on server read")


            # Launch new consumer threads if necessary
            while self.cnsr_queue.qsize() > self.cnsr_thrd_size:
                # Next launch if two more items in queue
                self.cnsr_thrd_size += 2

                c = Consumer(self)
                self.cnsr_thrd.append(c)
                c.start()

            while self.sync_queue.qsize() > 0:
                action = self.sync_queue.get_nowait()
                if action[0] == "exit":
                    self.quit()
                elif action[0] == "loadconf":
                    for path in action[1:]:
                        self.load_file(path)
                self.sync_queue.task_done()



    # Config methods

    def load_file(self, filename):
        """Load a configuration file

        Arguments:
        filename -- the path to the file to load
        """

        import os

        # Unexisting file, assume a name was passed, import the module!
        if not os.path.isfile(filename):
            return self.import_module(filename)

        from nemubot.tools.config import config_nodes
        from nemubot.tools.xmlparser import XMLParser

        try:
            p = XMLParser(config_nodes)
            config = p.parse_file(filename)
        except:
            logger.exception("Can't load `%s'; this is not a valid nemubot "
                             "configuration file." % filename)
            return False

        # Preset each server in this file
        for server in config.servers:
            srv = server.server(config)
            # Add the server in the context
            if self.add_server(srv, server.autoconnect):
                logger.info("Server '%s' successfully added." % srv.id)
            else:
                logger.error("Can't add server '%s'." % srv.id)

        # Load module and their configuration
        for mod in config.modules:
            self.modules_configuration[mod.name] = mod
            if mod.autoload:
                try:
                    __import__(mod.name)
                except:
                    logger.exception("Exception occurs when loading module"
                                     " '%s'", mod.name)


        # Load files asked by the configuration file
        for load in config.includes:
            self.load_file(load.path)


    # Events methods

    def add_event(self, evt, eid=None, module_src=None):
        """Register an event and return its identifiant for futur update

        Return:
        None if the event is not in the queue (eg. if it has been executed during the call) or
        returns the event ID.

        Argument:
        evt -- The event object to add

        Keyword arguments:
        eid -- The desired event ID (object or string UUID)
        module_src -- The module to which the event is attached to
        """

        if hasattr(self, "stop") and self.stop:
            logger.warn("The bot is stopped, can't register new events")
            return

        import uuid

        # Generate the event id if no given
        if eid is None:
            eid = uuid.uuid1()

        # Fill the id field of the event
        if type(eid) is uuid.UUID:
            evt.id = str(eid)
        else:
            # Ok, this is quite useless...
            try:
                evt.id = str(uuid.UUID(eid))
            except ValueError:
                evt.id = eid

        # TODO: mutex here plz

        # Add the event in its place
        t = evt.current
        i = 0 # sentinel
        for i in range(0, len(self.events)):
            if self.events[i].current > t:
                break
        self.events.insert(i, evt)

        if i == 0:
            # First event changed, reset timer
            self._update_event_timer()
            if len(self.events) <= 0 or self.events[i] != evt:
                # Our event has been executed and removed from queue
                return None

        # Register the event in the source module
        if module_src is not None:
            module_src.__nemubot_context__.events.append(evt.id)
        evt.module_src = module_src

        logger.info("New event registered: %s -> %s", evt.id, evt)
        return evt.id


    def del_event(self, evt, module_src=None):
        """Find and remove an event from list

        Return:
        True if the event has been found and removed, False else

        Argument:
        evt -- The ModuleEvent object to remove or just the event identifier

        Keyword arguments:
        module_src -- The module to which the event is attached to (ignored if evt is a ModuleEvent)
        """

        logger.info("Removing event: %s from %s", evt, module_src)

        from nemubot.event import ModuleEvent
        if type(evt) is ModuleEvent:
            id = evt.id
            module_src = evt.module_src
        else:
            id = evt

        if len(self.events) > 0 and id == self.events[0].id:
            self.events.remove(self.events[0])
            self._update_event_timer()
            if module_src is not None:
                module_src.__nemubot_context__.events.remove(id)
            return True

        for evt in self.events:
            if evt.id == id:
                self.events.remove(evt)

                if module_src is not None:
                    module_src.__nemubot_context__.events.remove(evt.id)
                return True
        return False


    def _update_event_timer(self):
        """(Re)launch the timer to end with the closest event"""

        # Reset the timer if this is the first item
        if self.event_timer is not None:
            self.event_timer.cancel()

        if len(self.events):
            logger.debug("Update timer: next event in %d seconds",
                         self.events[0].time_left.seconds)
            self.event_timer = threading.Timer(
                self.events[0].time_left.seconds + self.events[0].time_left.microseconds / 1000000 if datetime.now(timezone.utc) < self.events[0].current else 0,
                self._end_event_timer)
            self.event_timer.start()

        else:
            logger.debug("Update timer: no timer left")


    def _end_event_timer(self):
        """Function called at the end of the event timer"""

        while len(self.events) > 0 and datetime.now(timezone.utc) >= self.events[0].current:
            evt = self.events.pop(0)
            self.cnsr_queue.put_nowait(EventConsumer(evt))

        self._update_event_timer()


    # Consumers methods

    def add_server(self, srv, autoconnect=True):
        """Add a new server to the context

        Arguments:
        srv -- a concrete AbstractServer instance
        autoconnect -- connect after add?
        """

        if srv.id not in self.servers:
            self.servers[srv.id] = srv
            if autoconnect and not hasattr(self, "noautoconnect"):
                srv.open()
            return True

        else:
            return False


    # Modules methods

    def import_module(self, name):
        """Load a module

        Argument:
        name -- name of the module to load
        """

        if name in self.modules:
            self.unload_module(name)

        __import__(name)


    def add_module(self, module):
        """Add a module to the context, if already exists, unload the
        old one before"""
        module_name = module.__spec__.name if hasattr(module, "__spec__") else module.__name__

        if hasattr(self, "stop") and self.stop:
            logger.warn("The bot is stopped, can't register new modules")
            return

        # Check if the module already exists
        if module_name in self.modules:
            self.unload_module(module_name)

        # Overwrite print built-in
        def prnt(*args):
            if hasattr(module, "logger"):
                module.logger.info(" ".join([str(s) for s in args]))
            else:
                logger.info("[%s] %s", module_name, " ".join([str(s) for s in args]))
        module.print = prnt

        # Create module context
        from nemubot.modulecontext import ModuleContext
        module.__nemubot_context__ = ModuleContext(self, module)

        if not hasattr(module, "logger"):
            module.logger = logging.getLogger("nemubot.module." + module_name)

        # Replace imported context by real one
        for attr in module.__dict__:
            if attr != "__nemubot_context__" and type(module.__dict__[attr]) == ModuleContext:
                module.__dict__[attr] = module.__nemubot_context__

        # Register decorated functions
        import nemubot.hooks
        for s, h in nemubot.hooks.hook.last_registered:
            module.__nemubot_context__.add_hook(s, h)
        nemubot.hooks.hook.last_registered = []

        # Launch the module
        if hasattr(module, "load"):
            try:
                module.load(module.__nemubot_context__)
            except:
                module.__nemubot_context__.unload()
                raise

        # Save a reference to the module
        self.modules[module_name] = module


    def unload_module(self, name):
        """Unload a module"""
        if name in self.modules:
            self.modules[name].print("Unloading module %s" % name)

            # Call the user defined unload method
            if hasattr(self.modules[name], "unload"):
                self.modules[name].unload(self)
            self.modules[name].__nemubot_context__.unload()

            # Remove from the nemubot dict
            del self.modules[name]

            # Remove from the Python dict
            del sys.modules[name]
            for mod in [i for i in sys.modules]:
                if mod[:len(name) + 1] == name + ".":
                    logger.debug("Module '%s' also removed from system modules list.", mod)
                    del sys.modules[mod]

            logger.info("Module `%s' successfully unloaded.", name)

            return True
        return False


    def receive_message(self, srv, msg):
        """Queued the message for treatment

        Arguments:
        srv -- The server where the message comes from
        msg -- The message not parsed, as simple as possible
        """

        self.cnsr_queue.put_nowait(MessageConsumer(srv, msg))


    def quit(self):
        """Save and unload modules and disconnect servers"""

        self.datastore.close()

        if self.event_timer is not None:
            logger.info("Stop the event timer...")
            self.event_timer.cancel()

        logger.info("Stop consumers")
        k = self.cnsr_thrd
        for cnsr in k:
            cnsr.stop = True

        logger.info("Save and unload all modules...")
        k = list(self.modules.keys())
        for mod in k:
            self.unload_module(mod)

        logger.info("Close all servers connection...")
        k = list(self.servers.keys())
        for srv in k:
            self.servers[srv].close()

        self.stop = True


    # Treatment

    def check_rest_times(self, store, hook):
        """Remove from store the hook if it has been executed given time"""
        if hook.times == 0:
            if isinstance(store, dict):
                store[hook.name].remove(hook)
                if len(store) == 0:
                    del store[hook.name]
            elif isinstance(store, list):
                store.remove(hook)


def hotswap(bak):
    bak.stop = True
    if bak.event_timer is not None:
        bak.event_timer.cancel()
    bak.datastore.close()

    new = Bot(str(bak.ip), bak.modules_paths, bak.datastore)
    new.servers = bak.servers
    new.modules = bak.modules
    new.modules_configuration = bak.modules_configuration
    new.events = bak.events
    new.hooks = bak.hooks

    new._update_event_timer()
    return new
