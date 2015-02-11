# -*- coding: utf-8 -*-

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

from distutils.version import LooseVersion
from importlib.abc import Finder
from importlib.machinery import SourceFileLoader
import imp
import logging
import os
import sys

from nemubot import __version__
import nemubot.hooks
from nemubot.message import TextMessage
from nemubot.tools.xmlparser import parse_file, module_state

logger = logging.getLogger("nemubot.importer")


class ModuleFinder(Finder):

    def __init__(self, modules_paths, add_module):
        self.modules_paths = modules_paths
        self.add_module = add_module

    def find_module(self, fullname, path=None):
        # print ("looking for", fullname, "in", path)
        # Search only for new nemubot modules (packages init)
        if path is None:
            for mpath in self.modules_paths:
                # print ("looking for", fullname, "in", mpath)
                if os.path.isfile(os.path.join(mpath, fullname + ".py")):
                    return ModuleLoader(self.add_module, fullname,
                                        os.path.join(mpath, fullname + ".py"))
                elif os.path.isfile(os.path.join(os.path.join(mpath, fullname), "__init__.py")):
                    return ModuleLoader(self.add_module, fullname,
                                        os.path.join(
                                            os.path.join(mpath, fullname),
                                            "__init__.py"))
        # print ("not found")
        return None


class ModuleLoader(SourceFileLoader):

    def __init__(self, add_module, fullname, path):
        self.add_module = add_module
        SourceFileLoader.__init__(self, fullname, path)


    def load_module(self, fullname):
        module = SourceFileLoader.load_module(self, fullname)

        # Add the module to the global modules list
        if self.add_module(module):
            logger.info("Module '%s' successfully loaded.", module.__name__)
        else:
            logger.error("An error occurs while importing `%s'.", module.__name__)
            raise ImportError("An error occurs while importing `%s'."
                              % module.__name__)
        return module