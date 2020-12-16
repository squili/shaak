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

# pylint: disable=unsubscriptable-object   # pylint/issues/3882

from typing import Optional

from discord.ext import commands
from tortoise    import Tortoise

from shaak.settings import app_settings
from shaak.consts   import ResponseLevel
from shaak.models   import WordWatchWatch

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
            ctx.message.content = args or ''
            await command.reinvoke(await self.bot.get_context(ctx.message))
    
    @commands.command('debug.sql')
    async def debug_sql(self, ctx: commands.Context, *, query: str):

        conn = Tortoise.get_connection('default')
        resp = await conn.execute_query(query)
        await self.utils.respond(ctx, ResponseLevel.success, repr(resp))
    
    @commands.command('debug.guilds')
    async def debug_guilds(self, ctx: commands.Context):

        entries = []
        for guild in self.bot.guilds:
            entries.append(f'{guild.name} ({guild.id}) - {guild.member_count} members')
        await self.utils.list_items(ctx, entries)
    
    @commands.command(name='debug.usage_check')
    async def debug_usage_check(self, ctx: commands.Context):
        items = []
        for i in self.bot.guilds:
            watch_count = await WordWatchWatch.filter(guild_id=i.id).count()
            items.append(f'{i.name} ({i.id}): {watch_count}')
        await self.utils.list_items(ctx, items)