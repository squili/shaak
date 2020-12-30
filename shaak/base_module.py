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

import asyncio

from discord.ext import commands

from shaak.consts     import ModuleInfo, ResponseLevel
from shaak.custom_bot import CustomBot
from shaak.errors     import ModuleDisabled

class BaseModule(commands.Cog):
    
    meta = ModuleInfo(
        name='base_module',
        settings=None
    )

    def __init__(self, bot: CustomBot):
        
        self.bot   = bot
        self.utils = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
        self.initialized = asyncio.Event()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        
        if ctx.cog != self:
            return

        if isinstance(error, ModuleDisabled):
            await self.utils.respond(ctx, ResponseLevel.module_disabled, f'Module {type(self).meta.name} disabled!')
    
    async def cog_check(self, ctx: commands.Context):

        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        await self.bot.manager_ready.wait()
        await self.initialized.wait()

        module_settings = await self.meta.settings.get(guild_id=ctx.guild.id)
        if module_settings.enabled:
            return True
        else:
            raise ModuleDisabled()
    
    async def initialize(self):
        
        self.initialized.set()
