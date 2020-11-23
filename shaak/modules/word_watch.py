# pylint: disable=unsubscriptable-object # pylint/issues/3882
import re
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass

import discord
import ormar
from discord.ext import commands
from discord.errors import HTTPException

from shaak.base_module import BaseModule
from shaak.checks import has_privlidged_role
from shaak.consts import ModuleInfo, MatchType, watch_setting_map
from shaak.database import WWWatch, WWPingGroup, WWPing, Setting, redis
from shaak.helpers import link_to_message, mention2id, id2mention, MentionType, bold_segments, bool2str, getrange_s, commas, pluralize
from shaak.utils import ResponseLevel, Utils
from shaak.errors import InvalidId
from shaak.matcher import text_preprocess, pattern_preprocess, word_matches

@dataclass
class WatchCacheEntry:

    id:            int
    match_type:    MatchType
    pattern:       str
    compiled:      Any
    ping_group_id: Optional[int]
    auto_delete:   bool
    ignore_case:   bool

    def __hash__(self):
        return \
            hash(self.id) + \
            hash(self.match_type) + \
            hash(self.pattern) + \
            hash(self.compiled) + \
            hash(self.ping_group_id) + \
            hash(self.auto_delete) + \
            hash(self.ignore_case)

class WordWatch(BaseModule):
    
    meta = ModuleInfo(
        name='word_watch',
        flag=0b1
    )

    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.watch_cache: Dict[str, WatchCacheEntry] = {}
        self.bot.add_on_error_hooks(self.after_invoke_hook)
        self.extra_check(commands.has_permissions(administrator=True))
        self.extra_check(has_privlidged_role())
    
    async def add_to_cache(self, watch: WWWatch) -> WatchCacheEntry:

        if watch.guild_id not in self.watch_cache:
            self.watch_cache[watch.guild_id] = []
        
        cache_entry = WatchCacheEntry(
            id=watch.id,
            match_type=MatchType(watch.match_type),
            pattern=watch.pattern,
            auto_delete=watch.auto_delete,
            ignore_case=watch.ignore_case,
            compiled=None,
            ping_group_id=None
        )

        if watch.ping_group != None:
            cache_entry.ping_group_id = watch.ping_group.id

        if cache_entry.match_type == MatchType.regex:
            cache_entry.compiled = re.compile(cache_entry.pattern, re.IGNORECASE if cache_entry.ignore_case else 0)
        elif cache_entry.match_type == MatchType.word:
            cache_entry.compiled = pattern_preprocess(cache_entry.pattern)
        else:
            await watch.delete()
            return None

        self.watch_cache[watch.guild_id].append(cache_entry)
        return cache_entry

    async def initialize(self):
        
        for guild in self.bot.guilds:
            self.watch_cache[guild.id] = []
        
        for watch in await WWWatch.objects.all():
            if watch.guild_id not in self.watch_cache:
                await watch.delete()
            else:
                await self.add_to_cache(watch)
        
        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        await self.initialized.wait()
        
        if guild.id not in self.watch_cache:
            self.watch_cache[guild.id] = []
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
        if guild.id in self.watch_cache:
            del self.watch_cache[guild.id]

        await WWWatch.objects.delete(guild_id=guild.id)
        ping_groups = await WWPingGroup.objects.filter(guild_id=guild.id).all()
        for group in ping_groups:
            await WWPing.objects.delete(group=group)
            await group.delete()
    
    async def scan_message(self, message: discord.Message):

        await self.initialized.wait()
        
        if message.guild is None:
            return
        
        if await redis.sismember(self.redis_key(message.guild.id, 'ig_ch'), message.channel.id):
            return

        if message.channel.category_id and await redis.sismember(self.redis_key(message.guild.id, 'ig_ch'), message.channel.category_id):
            return

        if message.webhook_id == None:
            for role in message.author.roles:
                if await redis.sismember(self.redis_key(message.guild.id, 'ig_rl'), role.id):
                    return
        
        delete_message = False
        matches = set()
        processed_text = None
        for watch in self.watch_cache[message.guild.id]:

            if watch.match_type == MatchType.regex:
                found = watch.compiled.findall(message.content)
                if found:
                    delete_message = delete_message or watch.auto_delete
                    for match in found:
                        matches.add((
                            watch.pattern, match.start(0), match.end(0)
                        ))

            elif watch.match_type == MatchType.word:
                if processed_text == None:
                    processed_text = text_preprocess(message.content)
                found = word_matches(processed_text, watch.compiled)
                if found:
                    delete_message = delete_message or watch.auto_delete
                    for match in found:
                        matches.add((
                            watch.pattern, match[0], match[1]
                        ))

        if matches:
            log_channel_id = await redis.get(self.redis_key(message.guild.id, 'log'))
            if log_channel_id == None:
                return
                
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel == None:
                return

            deduped_patterns = set([o[0] for o in matches])
            pattern_list = commas([f"`{i}`" for i in deduped_patterns])

            description_entries = [
                bold_segments(message.content, [(i[1], i[2]) for i in matches]),
                '',
                f'User: {id2mention(message.author.id, MentionType.user)}',
                f'Pattern{pluralize("", "s", len(matches))}: {pattern_list}',
                f'Channel: {id2mention(message.channel.id, MentionType.channel)}',
                f'Time: {message.created_at.strftime("%d/%m/%y %I:%M:%S %p")}',
                f'Deleted: {bool2str(delete_message, "yes", "no")}',
                f'Message: {link_to_message(message)}'
            ]
            
            message_embed = discord.Embed(
                color=discord.Color(0xd22513),
                description='\n'.join(description_entries)
            )
            message_embed.set_author(
                name=f'{message.author.name}#{message.author.discriminator} triggered {pattern_list} in #{message.channel.name}',
                icon_url=message.author.avatar_url
            )

            content = await redis.get(self.redis_key(message.guild.id, 'head'))
            if content:
                content = content.format(
                    patterns=pattern_list,
                    channel=message.channel.name,
                    channel_reference=id2mention(message.channel.id, MentionType.channel),
                    user=f'{message.author.name}#{message.author.discriminator}',
                    user_ping=id2mention(message.author.id, MentionType.user),
                    user_id=message.author.id
                )

            await log_channel.send(content=content, embed=message_embed)

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

    @commands.command(name='ww.watch')
    async def ww_watch(self, ctx: commands.Context, watch_settings: str, *patterns: str):

        if len(patterns) == 0:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Please specify some patterns')
            return

        split_settings = [i.split('.') for i in watch_settings.replace(' ', '').split(',')]
        raw_settings = {
            'del': False,
            'cased': False,
            'type': None,
            'ping': None
        }
        for setting in split_settings:
            if len(setting) == 0:
                continue
            elif len(setting) == 1:
                raw_settings[setting[0]] = True
            elif len(setting) == 2:
                raw_settings[setting[0]] = setting[1]
            else:
                await self.utils.respond(ctx, ResponseLevel.general_error, f'Malformed setting {".".join(setting)}')
                return
        if raw_settings['type'] == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, "Didn't specify a pattern type")
            return
        
        parsed_settings = {}
        for setting_name in raw_settings:
            if setting_name not in watch_setting_map:
                await self.utils.respond(ctx, ResponseLevel.general_error, f'Invalid setting name {setting_name}')
                return
            try:
                parsed_settings[setting_name] = watch_setting_map[setting_name](raw_settings[setting_name])
            except (ValueError, IndexError, AttributeError):
                await self.utils.respond(ctx, ResponseLevel.general_error, f'Invalid setting {setting_name}.{raw_settings[setting_name]}')
                return
        
        if parsed_settings['type'] == MatchType.word and parsed_settings['cased']:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Match type `word` cannot be case sensitive')
            return
        
        if parsed_settings['ping']:
            try:
                ping_group = await WWPingGroup.objects.get(
                    guild_id=ctx.guild.id,
                    name=parsed_settings['head']
                )
            except ormar.NoMatch:
                await self.utils.respond(ctx, ResponseLevel.general_error, f'Invalid ping group {parsed_settings["ping"]}')
                return
        else:
            ping_group = None

        duplicates = 0
        updates = 0
        additions = 0
        for pattern in patterns:
            try:
                existing = await WWWatch.objects.get(
                    guild_id=ctx.guild.id,
                    pattern=pattern
                )
            except ormar.NoMatch:
                added = await WWWatch.objects.create(
                    guild_id=ctx.guild.id,
                    pattern=pattern,
                    match_type=parsed_settings['type'].value,
                    ping_group=ping_group,
                    auto_delete=parsed_settings['del'],
                    ignore_case=not parsed_settings['cased']
                )
                await self.add_to_cache(added)
                additions += 1
            else:
                # TODO: make this not so terrible
                something_changed = False
                if existing.match_type != parsed_settings['type'].value:
                    existing.match_type = parsed_settings['type'].value
                    something_changed = True
                if existing.ping_group == None:
                    if ping_group != None:
                        existing.ping_group = ping_group
                        something_changed = True
                elif existing.ping_group.name != parsed_settings['ping']:
                    existing.ping_group = ping_group
                    something_changed = True
                if existing.auto_delete != parsed_settings['del']:
                    existing.auto_delete = parsed_settings['del']
                    something_changed = True
                if existing.ignore_case == parsed_settings['cased']:
                    existing.ignore_case = not parsed_settings['cased']
                    something_changed = True
                if something_changed:
                    await existing.update()
                    for index, word in enumerate(self.watch_cache[ctx.guild.id]):
                        if word.id == existing.id:
                            del self.watch_cache[ctx.guild.id][index]
                            break
                    await self.add_to_cache(existing)
                    updates += 1
                else:
                    duplicates += 1
        
        message_parts = []
        if additions:
            message_parts.append(f'Added {additions} new word{pluralize("", "s", additions)}.')
        if updates:
            message_parts.append(f'Updated {updates} existing word{pluralize("", "s", updates)}.')
        if duplicates:
            message_parts.append(f'Ignored {duplicates} duplicate word{pluralize("", "s", duplicates)}.')
        
        await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts))
    
    async def list_words(self, ctx: commands.Context, filter_lambda: Optional[Callable] = None):

        if filter_lambda:
            filtered = [watch for watch in self.watch_cache[ctx.guild.id] if filter_lambda(watch)]
        else:
            filtered = self.watch_cache[ctx.guild.id]

        if len(filtered) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No watches found')
            return
        
        await self.utils.list_items(ctx, [
            f'{index+1}: {watch.pattern}' for index, watch in enumerate(filtered)
        ])
    
    @commands.command(name='ww.list')
    async def ww_list(self, ctx: commands.Context):

        await self.list_words(ctx)
    
    @commands.command(name='ww.clear_watches')
    async def ww_clear_watches(self, ctx: commands.Context):

        if ctx.guild.id in self.watch_cache:
            await WWWatch.objects.delete(guild_id=ctx.guild.id)
            self.watch_cache[ctx.guild.id] = []
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, 'I have no idea where I am')
    
    async def remove_word(self, ctx: commands.Context, index: int) -> bool:

        try:
            cache_entry: WatchCacheEntry = self.watch_cache[ctx.guild.id][index-1]
        except IndexError:
            return True

        try:
            watch = await WWWatch.objects.get(id=cache_entry.id)
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Index {index} not mapped to a valid ID')
            return False
        
        await watch.delete()
        del self.watch_cache[ctx.guild.id][index-1]
        return False

    @commands.command(name='ww.remove')
    async def ww_remove(self, ctx: commands.Context, *indexes: int):

        errors = []
        offset = 0
        for index in indexes:
            if await self.remove_word(ctx, index - offset):
                errors.append(index)
            else:
                offset += 1
        
        if errors:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Error removing {"indices" if len(errors) != 1 else "index"} {commas(getrange_s(errors))}')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.rremove')
    async def ww_rremove(self, ctx: commands.Context, *ranges: str):

        errors = []
        offset = 0
        to_delete = set()
        for range_ in ranges:
            lower, upper = [int(i) for i in range_.split('-')]
            to_delete.update(range(lower, upper+1))

        for index in to_delete:
            if await self.remove_word(ctx, index - offset):
                errors.append(index)
            else:
                offset += 1
        
        if errors:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Error removing {"indices" if len(errors) != 1 else "index"} {commas(getrange_s(errors))}')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.qremove')
    async def ww_qremove(self, ctx: commands.Context, *patterns: str):

        errors = []
        for pattern in patterns:

            try:
                watch = await WWWatch.objects.get(guild_id=ctx.guild.id, pattern=pattern)
            except ormar.NoMatch:
                errors.append(pattern)
                continue
            
            await watch.delete()
            for index, item in enumerate(self.watch_cache[ctx.guild.id]):
                if item.id == watch.id:
                    del self.watch_cache[ctx.guild.id][index]
                    break

        if errors:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Error removing pattern{"s" if len(errors) != 1 else ""} {commas(errors)}')
        else:
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
    async def ww_log(self, ctx: commands.Context, channel_reference: Optional[str] = None):

        if channel_reference:
            channel_id = mention2id(channel_reference, MentionType.channel)
            await redis.set(self.redis_key(ctx.guild.id, 'log'), channel_id)
        else:
            await redis.delete(self.redis_key(ctx.guild.id, 'log'))
        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.header')
    async def ww_header(self, ctx: commands.Context, *, header_message: Optional[str] = None):

        if header_message:
            await redis.set(self.redis_key(ctx.guild.id, 'head'), header_message)
        else:
            await redis.delete(self.redis_key(ctx.guild.id, 'head'))
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.add_ping')
    async def ww_add_ping(self, ctx: commands.Context, group_name: str, ping: str):

        # TODO: implement

        await self.utils.respond(ctx, ResponseLevel.forbidden, 'Not implemented yet')
    
    @commands.command(name='ww.remove_ping')
    async def ww_remove_ping(self, ctx: commands.Context, group_name: str, ping: str):

        # TODO: implement

        await self.utils.respond(ctx, ResponseLevel.forbidden, 'Not implemented yet')
    
    @commands.command(name='ww.delete_group')
    async def ww_delete_group(self, ctx: commands.Context, group_name: str):

        # TODO: implement

        await self.utils.respond(ctx, ResponseLevel.forbidden, 'Not implemented yet')