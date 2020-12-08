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

import asyncio
import time
import random
from typing   import List, Optional, Union, Callable, TypeVar, Coroutine
from datetime import datetime

import discord
from discord.ext import commands

from shaak.consts      import ResponseLevel, response_map, color_green, MentionType
from shaak.models      import GuildSettings, GlobalSettings
from shaak.helpers     import chunks, platform_info, commas, getrange_s
from shaak.settings    import product_settings
from shaak.extra_types import GeneralChannel
from shaak.checks      import has_privlidged_role_check

_T = TypeVar('T')

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

        if message.guild is None:
            be_loud = True
        else:
            be_loud = False
            if response:
                if response_level == ResponseLevel.success and response:
                    be_loud = True
                else:
                    guild_settings: GuildSettings = await GuildSettings.get(guild_id=message.guild.id)
                    if guild_settings.verbosity == None:
                        global_settings = await GlobalSettings.get(id=0)
                        be_loud = global_settings.default_verbosity
                    else:
                        be_loud = guild_settings.verbosity
        
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
    
    async def reaction_wait(self, ctx: commands.Context, target_message: discord.Message,
                            listen_for: List[str], timeout: float = 30.0) -> Optional[str]:
        
        def check(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.message == target_message and user == ctx.author and str(reaction) in listen_for
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)
        except asyncio.TimeoutError:
            return None
        else:
            return str(reaction)
    
    async def list_items(self, ctx: commands.Context, items: List[str], escape: bool = False,
                         title: Optional[str] = None, custom_embed: Optional[Coroutine] = None):

        if len(items) == 0:
            return
        
        pages = chunks(items, 10)
        page_index = 0
        if custom_embed == None:
            text = '\n'.join([item for item in pages[page_index]])
            if escape:
                text = f'```{text}```'
            embed = discord.Embed(
                description=text,
                title=title
            )
            if len(pages) > 1:
                embed.set_footer(text=f'1/{len(pages)}')
        else:
            embed = await custom_embed(ctx, pages[page_index], page_index, len(pages))
        new_message = await ctx.send(embed=embed)
        
        if len(pages) == 1:
            return
        
        for emoji in ['⏪', '◀', '▶', '⏩']:
            await new_message.add_reaction(emoji)
        
        def check(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.message == new_message and user == ctx.author and str(reaction) in ['⏪', '◀', '▶', '⏩']
        
        while True:
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            except asyncio.TimeoutError:
                break
            else:
                reaction_string = str(reaction.emoji)
                if reaction_string == '◀':
                    page_index = max(page_index - 1, 0)
                elif reaction_string == '▶':
                    page_index = min(page_index + 1, len(pages) - 1)
                elif reaction_string == '⏪':
                    page_index = 0
                elif reaction_string == '⏩':
                    page_index = len(pages) - 1
                if custom_embed == None:
                    text = '\n'.join([item for item in pages[page_index]])
                    if escape:
                        text = f'```{text}```'
                    embed = discord.Embed(
                        description=text,
                        title=title
                    )
                    embed.set_footer(text=f'{page_index+1}/{len(pages)}')
                else:
                    embed = await custom_embed(ctx, pages[page_index], page_index, len(pages))
                await new_message.edit(embed=embed)
                await reaction.remove(user)
        
        for emoji in ['⏪', '◀', '▶', '⏩']:
            await new_message.clear_reaction(emoji)
    
    async def _aggressive_resolve(self, some_id: int, calm_method: Callable, aggressive_method: Coroutine, return_type: _T) -> Optional[_T]:

        optimistic = calm_method(some_id)
        if optimistic == None:
            try:
                return await aggressive_method(some_id)
            except discord.NotFound:
                return None
        return optimistic

    async def aggressive_resolve_user(self, user_id: int) -> Optional[discord.User]:
        return await self._aggressive_resolve(user_id, self.bot.get_user, self.bot.fetch_user, discord.User)

    async def aggressive_resolve_channel(self, channel_id: int) -> Optional[GeneralChannel]:
        return await self._aggressive_resolve(channel_id, self.bot.get_channel, self.bot.fetch_channel, GeneralChannel)

    async def guess_id(self, some_id: int, guild: Optional[discord.Guild] = None) -> Optional[MentionType]:

        user = await self.aggressive_resolve_user(some_id)
        if user == None:
            channel = await self.aggressive_resolve_channel(some_id)
            if channel == None:
                if guild == None:
                    return None
                else:
                    role = guild.get_role(some_id)
                    if role == None:
                        return None
                    else:
                        return MentionType.role
            else:
                return MentionType.channel
        else:
            return MentionType.user
    
    async def log_background_error(self, guild: discord.Guild, error: Exception):

        guild_settings = await GuildSettings.get(guild_id=guild.id)
        if guild_settings.error_channel == None:
            return
        log_channel = self.bot.get_channel(guild_settings.error_channel)
        embed = discord.Embed(
            description=str(error)
        )
        embed.set_footer(text='Error report')
        await log_channel.send(embed=embed)

    @commands.command('about')
    async def about(self, ctx: commands.Context):

        embed = discord.Embed(
            color=color_green,
            title=f'{product_settings.bot_name} v{product_settings.bot_version} by {product_settings.author_name}',
            description='\n'.join([
                f'Bot source: {product_settings.bot_repo}',
                f'Docs: {product_settings.bot_docs}',
                f'Support the author: {product_settings.author_donate}',
                f'Platform: {platform_info()}'
            ]),
            url=product_settings.author_page
        )

        await ctx.send(embed=embed)
    
    @commands.command('ping')
    async def ping(self, ctx: commands.Context):

        now = datetime.now()
        message_receive = round((now - ctx.message.created_at).microseconds/1000)

        def reaction_check(reaction: discord.Reaction, user: discord.User) -> bool:
            return user == self.bot.user and reaction.message.id == ctx.message.id and reaction.emoji == '🏓'

        wait_task = asyncio.create_task(self.bot.wait_for('reaction_add', check=reaction_check, timeout=10.0))
        start = time.time()
        await ctx.message.add_reaction('🏓')
        try:
            await asyncio.wait_for(wait_task, 15.0)
        except asyncio.TimeoutError:
            await self.respond(ctx, ResponseLevel.internal_error, 'Reaction ping timed out')
        end = time.time()
        reaction_roundtrip = round((end-start)*1000)
        await ctx.message.remove_reaction('🏓', self.bot.user)

        nonce = random.randint(0, 0xFFFFFFFF)
        def message_check(message: discord.Message) -> bool:
            return message.author == self.bot.user and message.nonce == nonce
        
        wait_task = asyncio.create_task(self.bot.wait_for('message', check=message_check, timeout=10.0))
        start = time.time()
        new_message = await ctx.send('🏓', nonce=nonce)
        try:
            await asyncio.wait_for(wait_task, 15.0)
        except asyncio.TimeoutError:
            await self.respond(ctx, ResponseLevel.internal_error, 'Message ping timed out')
        end = time.time()
        message_roundtrip = round((end-start)*1000)

        await new_message.edit(content='', embed=discord.Embed(
            color=color_green,
            description='\n'.join([
                f'Message receive: {message_receive}ms',
                f'Reaction roundtrip: {reaction_roundtrip}ms',
                f'Message roundtrip: {message_roundtrip}ms',
            ])
        ))
    
    @commands.command('massban')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check(), commands.guild_only())
    async def massban(self, ctx: commands.Context, *ids: int):

        await ctx.message.add_reaction('🔄')

        errors = []
        for index, id in enumerate(ids):
            try:
                await ctx.guild.ban(discord.Object(id=id), reason=f'Massban by {ctx.author.id}')
            except Exception as e:
                errors.append(index+1)
        
        await ctx.message.remove_reaction('🔄', self.bot.user)
        
        if len(errors) > 0:
            await self.respond(ctx, ResponseLevel.general_error, f'Failed banning {commas(getrange_s(errors))}')
        else:
            await self.respond(ctx, ResponseLevel.success)
    
    @commands.command('massrole')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check(), commands.guild_only())
    async def massrole(self, ctx: commands.Context, role: commands.RoleConverter(), *members: commands.MemberConverter()):

        await ctx.message.add_reaction('🔄')

        errors = []
        for index, member in enumerate(members):
            if role in member.roles:
                continue
            try:
                await member.add_roles(role, reason=f'Massrole by {ctx.author.id}')
            except Exception as e:
                errors.append(index+1)
        
        await ctx.message.remove_reaction('🔄', self.bot.user)

        if len(errors) > 0:
            await self.respond(ctx, ResponseLevel.general_error, f'Failed roling {commas(getrange_s(errors))}')
        else:
            await self.respond(ctx, ResponseLevel.success)
