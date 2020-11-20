import re

import discord
import ormar
from discord.ext import commands

from shaak.base_module import BaseModule
from shaak.checks import has_privlidged_role
from shaak.consts import ModuleInfo
from shaak.database import SusWord, Setting, redis
from shaak.helpers import link_to_message, mention2id, id2mention, MentionType, bold_segment, bool2str
from shaak.utils import ResponseLevel, Utils
from shaak.errors import InvalidId

class WordWatch(BaseModule):
    
    meta = ModuleInfo(
        name='word_watch',
        flag=0b1
    )

    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.word_cache = {}
        self.bot.add_on_error_hooks(self.after_invoke_hook)
        self.extra_check(commands.has_permissions(administrator=True))
        self.extra_check(has_privlidged_role())
    
    async def initialize(self):
        
        for guild in self.bot.guilds:
            self.word_cache[guild.id] = []
        
        for sus in await SusWord.objects.all():
            if sus.server_id not in self.word_cache:
                await sus.delete()
            else:
                self.word_cache[sus.server_id].append([sus.id, re.compile(sus.regex), sus.auto_delete])
        
        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        await self.initialized.wait()
        
        if guild.id not in self.word_cache:
            self.word_cache[guild.id] = []
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
        if guild.id in self.word_cache:
            await SusWord.objects.delete(server_id=guild.id)
            del self.word_cache[guild.id]
    
    async def scan_message(self, message: discord.Message):

        await self.initialized.wait()
        
        if message.guild is None:
            return
        
        if not isinstance(message.author, discord.Member): # sometimes the author isn't a member
            member = message.guild.get_member(message.author.id)
            if member is None: # it might not even been in the member cache!
                message.author = await message.guild.fetch_member(message.author.id)
            else:
                message.author = member
        
        if await redis.sismember(self.redis_key(message.guild.id, 'ig_ch'), message.channel.id):
            return

        if message.channel.category_id and await redis.sismember(self.redis_key(message.guild.id, 'ig_ch'), message.channel.category_id):
            return

        for role in message.author.roles:
            if await redis.sismember(self.redis_key(message.guild.id, 'ig_rl'), role.id):
                return
        
        stop = False
        for sus in self.word_cache[message.guild.id]:
            if (match := sus[1].search(message.content)):
                if sus[2]:
                    await message.delete()
                    stop = True
                
                log_channel_id = await redis.get(self.redis_key(message.guild.id, 'log'))
                if log_channel_id == None:
                    return
                    
                log_channel = self.bot.get_channel(int(log_channel_id))
                if log_channel == None:
                    return

                description_entries = [
                    bold_segment(message.content, match.start(0), match.end(0)),
                    '',
                    f'User: {id2mention(message.author.id, MentionType.user)}',
                    f'Pattern: /{sus[1].pattern}/',
                    f'Channel: {id2mention(message.channel.id, MentionType.channel)}',
                    f'Time: {message.created_at.strftime("%d/%m/%y %I:%M:%S %p")}',
                    f'Deleted: {bool2str(sus[2], "yes", "no")}',
                    f'Message: {link_to_message(message)}'
                ]
                
                message_embed = discord.Embed(
                    color=discord.Color(0xd22513),
                    description='\n'.join(description_entries)
                )
                message_embed.set_author(
                    name=f'{message.author.name}#{message.author.discriminator} triggered /{sus[1].pattern}/ in #{message.channel.name}',
                    icon_url=message.author.avatar_url
                )

                content = None
                ping = await redis.get(self.redis_key(message.guild.id, 'ping'))
                if ping:
                    content = id2mention(int(ping), MentionType.role)

                await log_channel.send(content=content, embed=message_embed)
            if stop: break

    async def after_invoke_hook(self, ctx: commands.Context):

        await self.scan_message(ctx.message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author == self.bot.user:
            return
        
        if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
            return

        server_prefix = await self.bot.command_prefix(self.bot, message)
        if not message.content.startswith(server_prefix):
            await self.scan_message(message)

    async def add_to_watch(self, server_id: int, regex: str, auto_delete: bool) -> str:

        if len(regex) > 1000:
            return 'Pattern too long'

        try:
            existing = await SusWord.objects.get(server_id=server_id, regex=regex)
        except ormar.NoMatch:
            added = await SusWord.objects.create(server_id=server_id, regex=regex, auto_delete=auto_delete)
            self.word_cache[server_id].append([added.id, re.compile(regex), auto_delete])

        else:
            if existing.auto_delete == auto_delete:
                return 'Word already exists'
            else:
                await existing.update(auto_delete=auto_delete)
                for word in self.word_cache[server_id]:
                    if word[0] == existing.id:
                        word[2] = auto_delete

    @commands.command(name='ww.watch')
    async def ww_watch(self, ctx: commands.Context, *regexes: str):

        for regex in regexes:
            resp = await self.add_to_watch(ctx.guild.id, regex, False)
            if resp:
                await self.utils.respond(ctx, ResponseLevel.general_error, resp)
            else:
                await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.censor')
    async def ww_censor(self, ctx: commands.Context, *regexes: str):

        for regex in regexes:
            resp = await self.add_to_watch(ctx.guild.id, regex, True)
            if resp:
                await self.utils.respond(ctx, ResponseLevel.general_error, resp)
            else:
                await self.utils.respond(ctx, ResponseLevel.success)
    
    async def list_words(self, ctx, suses, check_lambda):

        if len(suses) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No words found')
            return
        
        await self.utils.list_items(ctx, [
            f'{index+1}: {item[1].pattern} ({"censor" if item[2] else "watch"})' for index, item in enumerate(suses) if check_lambda(item)
        ])
    
    @commands.command(name='ww.list')
    async def ww_list(self, ctx: commands.Context):

        await self.list_words(ctx, self.word_cache[ctx.guild.id], lambda x: True)
    
    @commands.command(name='ww.watched')
    async def ww_watched(self, ctx: commands.Context):

        await self.list_words(ctx, self.word_cache[ctx.guild.id], lambda x: not x[2])
    
    @commands.command(name='ww.censored')
    async def ww_censored(self, ctx: commands.Context):

        await self.list_words(ctx, self.word_cache[ctx.guild.id], lambda x: x[2])
    
    @commands.command(name='ww.clear_words')
    async def ww_clear_words(self, ctx: commands.Context):
        
        if ctx.guild.id in self.word_cache:
            await SusWord.objects.delete(server_id=ctx.guild.id)
            self.word_cache[ctx.guild.id] = []
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, 'I have no idea where I am')
    
    async def remove_word(self, ctx: commands.Context, index: int) -> bool:

        try:
            word = self.word_cache[ctx.guild.id][index-1]
        except IndexError:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Index {index} not found')
            return False

        try:
            sus = await SusWord.objects.get(id=word[0])
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Index {index} not mapped to a valid ID')
            return False
        
        await sus.delete()
        del self.word_cache[ctx.guild.id][index-1]
        return True

    @commands.command(name='ww.remove')
    async def ww_remove(self, ctx: commands.Context, *indexes: int):
    
        x = 0
        for index in indexes:
            if not await self.remove_word(ctx, index - x):
                return
            x += 1

        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.rremove')
    async def ww_rremove(self, ctx: commands.Context, lower: int, upper: int):
    
        for _ in range(lower, upper + 1):
            if not await self.remove_word(ctx, lower):
                return

        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.qremove')
    async def ww_qremove(self, ctx: commands.Context, *patterns: str):
    
        for pattern in patterns:

            try:
                sus = await SusWord.objects.get(server_id=ctx.guild.id, regex=pattern)
            except ormar.NoMatch:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Not found')
                return
            
            await sus.delete()
            for index, item in enumerate(self.word_cache[ctx.guild.id]):
                if item[0] == sus.id:
                    del self.word_cache[ctx.guild.id][index]
                    break

        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.ignore')
    async def ww_ignore(self, ctx: commands.Context, reference_type: str, *references: str):

        if reference_type not in ['role', 'channel']:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid reference type')
            return

        for reference in references:
            if reference_type == 'channel':
                await redis.sadd(self.redis_key(ctx.guild.id, 'ig_ch'), mention2id(reference, MentionType.channel))
            else:
                await redis.sadd(self.redis_key(ctx.guild.id, 'ig_rl'), mention2id(reference, MentionType.role))

        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.ignored')
    async def ww_ignored(self, ctx: commands.Context):
        
        ignored_channels = await redis.smembers(self.redis_key(ctx.guild.id, 'ig_ch'))
        ignored_roles = await redis.smembers(self.redis_key(ctx.guild.id, 'ig_rl'))
        if len(ignored_channels) + len(ignored_roles) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'Nothing ignored')
            return
        await self.utils.list_items(ctx,
            [id2mention(i, MentionType.channel) for i in ignored_channels] + \
            [id2mention(i, MentionType.role)    for i in ignored_roles]
        )
    
    @commands.command(name='ww.unignore')
    async def ww_unignore(self, ctx: commands.Context, *references: str):

        for reference in references:
            try:
                id = mention2id(reference, MentionType.channel)
            except InvalidId:
                id = mention2id(reference, MentionType.role)
            await redis.srem(self.redis_key(ctx.guild.id, 'ig_ch'), id)
            await redis.srem(self.redis_key(ctx.guild.id, 'ig_rl'), id)
        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.log')
    async def ww_log(self, ctx: commands.Context, channel_reference: str):

        channel_id = mention2id(channel_reference, MentionType.channel)
        await redis.set(self.redis_key(ctx.guild.id, 'log'), channel_id)
        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.ping')
    async def ww_ping(self, ctx: commands.Context, role_reference: str):

        if role_reference == 'clear':
            await redis.delete(self.redis_key(ctx.guild.id, 'ping'))
        else:
            role_id = mention2id(role_reference, MentionType.role)
            await redis.set(self.redis_key(ctx.guild.id, 'ping'), role_id)
        await self.utils.respond(ctx, ResponseLevel.success)