# pylint: disable=unsubscriptable-object   # pylint/issues/3882

import asyncio
from copy import deepcopy
from typing import Optional

from discord.ext import commands
from tortoise import Tortoise

from shaak.settings import app_settings
from shaak.consts import ResponseLevel

class Debug(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utils')

    async def cog_check(self, ctx: commands.Context):

        if ctx.author.id == app_settings.owner_id:
            return True
        else:
            raise commands.CheckFailure('👀')
    
    @commands.command('debug.sudo')
    async def debug_sudo(self, ctx: commands.Context, command_name: str, *, args: Optional[str]):

        command = self.bot.get_command(command_name)
        if command == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid command name')
        else:
            ctx.message.content = args
            await command.reinvoke(await self.bot.get_context(ctx.message.content))
    
    @commands.command('debug.sql')
    async def debug_query(self, ctx: commands.Context, *, query: str):

        conn = Tortoise.get_connection('default')
        resp = await conn.execute_query(query)
        await self.utils.respond(ctx, ResponseLevel.success, repr(resp))