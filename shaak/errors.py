'''
This file is part of Shaak.

Shaak is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Shaak is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Shaak.  If not, see <https://www.gnu.org/licenses/>.
'''

from discord.ext import commands

class ModuleDisabled(commands.CheckFailure): pass
class NotAllowed(commands.CheckFailure): pass
class NotWhitelisted(commands.CheckFailure): pass
class InvalidId(Exception):
    def __init__(self, message='Invalid Id'):
        self.message = message
    def __str__(self):
        return self.message
