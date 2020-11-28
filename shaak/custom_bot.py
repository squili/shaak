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

import asyncio

import discord
from discord.ext import commands

from shaak.errors import ModuleDisabled, NotAllowed, InvalidId
from shaak.consts import ResponseLevel
from shaak.models import GuildSettings, GlobalSettings

class CustomBot(commands.Bot):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.manager_ready = asyncio.Event()
        self.on_error_hooks = []
    
    def add_on_error_hooks(self, coro):

        self.on_error_hooks.append(coro)

    async def on_command_error(self, ctx: commands.Context, error: Exception):

        for coro in self.on_error_hooks:
            await coro(ctx)
        
        if not hasattr(self, 'utils'):
            self.utils = self.get_cog('Utils')
        
        if isinstance(error, commands.CheckAnyFailure):
            if len(error.errors) > 0:
                error = error.errors[0]
        elif isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, (ModuleDisabled, commands.CommandNotFound)):
            return
        elif isinstance(error, (commands.MissingPermissions, NotAllowed)):
            await self.utils.respond(ctx, ResponseLevel.forbidden, 'You do not have permission to run this command')
        elif isinstance(error, discord.HTTPException) and error.code == 10008:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'HTTP error code {error.code}')
        elif isinstance(error, (commands.CommandError, InvalidId)):
            await self.utils.respond(ctx, ResponseLevel.general_error, str(error) or type(error).__name__)
        elif isinstance(error, NotImplementedError):
            try:
                await self.utils.respond(ctx, ResponseLevel.internal_error, 'Not implemented')
            except NotImplementedError:
                await ctx.send('Not implemented')
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Unhandled error of type {type(error).__name__}. Check the console!')
            raise error

async def get_command_prefix(bot: CustomBot, message: discord.Message) -> str:
    
    await bot.manager_ready.wait()
    if message.guild != None:
        guild_settings: GuildSettings = await GuildSettings.get(guild_id=message.guild.id)
        if guild_settings.prefix:
            return guild_settings.prefix
    global_settings = await GlobalSettings.get(id=0)
    return global_settings.default_prefix