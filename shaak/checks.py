'''
Shaak Discord moderation bot
Copyright (C) 2020 Squili

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

from discord.ext import commands

from shaak.errors  import NotAllowed
from shaak.helpers import check_privildged

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
