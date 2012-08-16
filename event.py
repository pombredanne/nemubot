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

from datetime import datetime
from datetime import timedelta

class ModuleEvent:
    def __init__(self, func=None, func_data=None, check=None, cmp_data=None,
                 intervalle=60, call=None, call_data=None, times=1):
        # What have we to check?
        self.func = func
        self.func_data = func_data

        # How detect a change?
        self.check = check
        if cmp_data is not None:
            self.cmp_data = cmp_data
        elif self.func is not None:
            if self.func_data is None:
                self.cmp_data = self.func()
            elif isinstance(self.func_data, dict):
                self.cmp_data = self.func(**self.func_data)
            else:
                self.cmp_data = self.func(self.func_data)

        self.intervalle = timedelta(seconds=intervalle)
        self.end = None

        # What should we call when
        self.call = call
        if call_data is not None:
            self.call_data = call_data
        else:
            self.call_data = func_data

        # How many times do this event?
        self.times = times


    @property
    def next(self):
        """Return the date of the next check"""
        if self.times != 0:
            if self.end is None:
                self.end = datetime.now() + self.intervalle
            elif self.end < datetime.now():
                self.end += self.intervalle
            return self.end
        return None

    @property
    def current(self):
        """Return the date of the near check"""
        if self.times != 0:
            if self.end is None:
                self.end = datetime.now() + self.intervalle
            return self.end
        return None

    @property
    def time_left(self):
        """Return the time left before/after the near check"""
        if self.current is not None:
            return self.current - datetime.now()
        return 99999

    def launch_check(self):
        if self.func is None:
            d = self.func_data
        elif self.func_data is None:
            d = self.func()
        elif isinstance(self.func_data, dict):
            d = self.func(**self.func_data)
        else:
            d = self.func(self.func_data)
        #print ("do test with", d, self.cmp_data)

        if self.check is None:
            r = True
        elif self.cmp_data is None:
            r = self.check(d)
        elif isinstance(self.cmp_data, dict):
            r = self.check(d, **self.cmp_data)
        else:
            r = self.check(d, self.cmp_data)

        if r:
            self.times -= 1
            if self.call_data is None:
                self.call()
            elif isinstance(self.call_data, dict):
                self.call(**self.call_data)
            else:
                self.call(self.call_data)