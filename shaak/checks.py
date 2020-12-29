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

from shaak.errors   import NotAllowed
from shaak.helpers  import check_privildged
from shaak.settings import app_settings

def has_privlidged_role_check():

    async def predicate(ctx: commands.Context):

        privildged = await check_privildged(ctx.guild, ctx.author)
        if privildged == None:
            return False
        elif privildged == True:
            return True
        elif privildged == False:
            raise NotAllowed()
    
    return commands.check(predicate)

def is_owner_check():

    async def predicate(ctx: commands.Context):

        if ctx.author.id == app_settings.owner_id:
            return True
        else:
            raise commands.CheckFailure('👀')
    
    return commands.check(predicate)