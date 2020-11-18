# pylint: disable=unsubscriptable-object   # pylint/issues/3637

import asyncio
from typing import List, Optional, Union

import discord
from discord.ext import commands

from shaak.consts import ResponseLevel, response_map
from shaak.database import Setting, GlobalSetting
from shaak.helpers import chunks

class Utils(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def respond(self, ctx_or_message: Union[commands.Context, discord.Message], response_level: ResponseLevel, response: Optional[str] = None):
        
        if response_level not in response_map:
            raise RuntimeError(f'Invalid response level {repr(response_level)}')

        if isinstance(ctx_or_message, commands.Context):
            message: discord.Message = ctx_or_message.message
        else:
            message: discord.Message = ctx_or_message
        
        response_emoji, response_color = response_map[response_level]

        be_loud = False
        if response:
            if response_level == ResponseLevel.success:
                be_loud = True
            else:
                server_settings: Setting = await Setting.objects.get(server_id=message.guild.id)
                if server_settings.verbose_errors == None:
                    global_settings: GlobalSetting = await GlobalSetting.objects.get(id=0)
                    be_loud = global_settings.verbose_errors
                else:
                    be_loud = server_settings.verbose_errors
        
        if be_loud:
            
            embed = discord.Embed(
                color=response_color,
                description=response
            )
            
            if isinstance(message, commands.Context):
                await message.send(embed=embed)
            else:
                await message.channel.send(embed=embed)
        else:

            await message.add_reaction(response_emoji)
    
    async def list_items(self, ctx: commands.Context, items: List[str]):

        if len(items) == 0:
            return
        
        pages = chunks(items, 10)
        page_index = 0
        
        new_message = await ctx.send(embed=discord.Embed(
            description='\n'.join([item for item in pages[page_index]])
        ))
        
        if len(pages) == 1:
            return
        
        await new_message.add_reaction('◀')
        await new_message.add_reaction('▶')
        
        def check(reaction: discord.Reaction, user: discord.User):
            return reaction.message.channel.id == ctx.channel.id and user == ctx.author and str(reaction.emoji) in ['◀', '▶']
        
        while True:
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=10.0, check=check)
            except asyncio.TimeoutError:
                break
            else:
                reaction_string = str(reaction.emoji)
                if reaction_string == '◀':
                    page_index = max(page_index - 1, 0)
                elif reaction_string == '▶':
                    page_index = min(page_index + 1, len(pages) - 1)
                await new_message.edit(embed=discord.Embed(
                    description='\n'.join([item for item in pages[page_index]])
                ))
                await reaction.remove(user)
        
        await new_message.clear_reaction('▶')
        await new_message.clear_reaction('◀')

    async def aggressive_resolve_user(self, user_id: str) -> Optional[discord.User]:

        optimistic = self.bot.get_user(user_id)
        if optimistic == None:
            try:
                return await self.bot.fetch_user(user_id)
            except discord.NotFound:
                return None
        return optimistic