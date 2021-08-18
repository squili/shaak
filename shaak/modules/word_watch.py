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

import time
import logging
import io
import string
import re
from dataclasses import dataclass
from typing      import Any, Dict, List, Optional, Tuple, Set

import discord
from discord.errors      import HTTPException
from discord.ext         import commands
from tortoise.exceptions import DoesNotExist

from shaak.base_module import BaseModule
from shaak.checks      import has_privlidged_role_check, is_owner_check
from shaak.consts      import MatchType, ModuleInfo, watch_setting_map
from shaak.helpers     import (MentionType, between_segments, bool2str, commas,
                               get_int_ranges, getrange_s, id2mention,
                               link_to_message, mention2id, pluralize,
                               resolve_mention, possesivize, str2bool,
                               DiscardingQueue)
from shaak.matcher  import pattern_preprocess, text_preprocess, word_matches, find_all_contains
from shaak.models   import (WordWatchSettings, WordWatchPingGroup, WordWatchPing,
                            WordWatchWatch, WordWatchIgnore, Guild)
from shaak.settings import product_settings
from shaak.utils    import ResponseLevel

logger = logging.getLogger('shaak_word_watch')

@dataclass
class WatchCacheEntry:

    id:          int
    compiled:    Any
    ignore_case: bool
    auto_delete: bool
    match_type:  int
    pattern:     str
    ban:         int

    def __hash__(self):
        return self.id

class WordWatch(BaseModule):
    
    meta = ModuleInfo(
        name='word_watch',
        settings=WordWatchSettings
    )

    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.watch_cache:  Dict[int, List[WatchCacheEntry]] = {}
        self.ignore_cache: Dict[int, Set[int]] = {}
        self.scan_queue = DiscardingQueue(0x400)
        self.bot.add_on_error_hooks(self.after_invoke_hook)
    
    async def add_to_cache(self, watch: WordWatchWatch) -> None:

        if watch.guild.id not in self.watch_cache:
            self.watch_cache[watch.guild.id] = []
        
        cache_entry = WatchCacheEntry(
            id=watch.id,
            compiled=None,
            ignore_case=watch.ignore_case,
            auto_delete=watch.auto_delete,
            match_type=watch.match_type,
            pattern=watch.pattern,
            ban=watch.ban
        )

        try:
            if watch.match_type == MatchType.word.value:
                cache_entry.compiled = pattern_preprocess(watch.pattern)
            elif watch.match_type == MatchType.contains.value:
                pass
            elif watch.match_type == MatchType.regex.value:
                cache_entry.compiled = re.compile(watch.pattern, re.IGNORECASE if watch.ignore_case else 0)
            else:
                logger.error(f'bad watch cache entry with id {watch.id}: {watch.match_type} is not a valid match type. this should never happen!')
                return
        except Exception:
            # if preprocessing fails, remove it from the database. if we don't do this,
            # invalid entries will be added to startup and cause modules to never fully load
            await watch.delete()
            return

        self.watch_cache[watch.guild.id].append(cache_entry)
        return

    async def initialize(self):

        for guild in self.bot.guilds:
            self.watch_cache[guild.id] = []
            self.ignore_cache[guild.id] = set()
        
        for watch in await WordWatchWatch.all().prefetch_related('guild', 'group'):
            await self.add_to_cache(watch)
        
        for ignore in await WordWatchIgnore.all().prefetch_related('guild'):
            if ignore.guild.id in self.ignore_cache:
                self.ignore_cache[ignore.guild.id].add(ignore.target_id)
            else:
                logger.warn(f'orphaned ignore entry with id {ignore.id}')
                await ignore.delete()

        self.scan_task = self.bot.loop.create_task(self.scan_loop())

        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        await self.initialized.wait()
        
        if guild.id not in self.watch_cache:
            self.watch_cache[guild.id] = []
            self.ignore_cache[guild.id] = set()
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):

        await self.initialized.wait()
        
        if guild.id in self.watch_cache:
            del self.watch_cache[guild.id]

        if guild.id in self.ignore_cache:
            del self.ignore_cache[guild.id]
        
    async def scan_message(self, message: discord.Message):

        start_time = time.time()
        try:
            
            if message.guild is None:
                return
            
            if message.author.bot:
                return
            
            if message.guild.id not in self.ignore_cache:
                return
            
            if message.channel.id in self.ignore_cache[message.guild.id]:
                return

            if message.channel.category_id and message.channel.category_id in self.ignore_cache[message.guild.id]:
                return
            
            if message.author.id in self.ignore_cache[message.guild.id]:
                return
            
            check_member = message.webhook_id == None
            if isinstance(message.author, discord.User):
                try:
                    message.author = await message.guild.fetch_member(message.author.id)
                except discord.HTTPException:
                    check_member = False

            if check_member:
                for role in message.author.roles:
                    if role.id in self.ignore_cache[message.guild.id]:
                        return
            
            delete_message = False
            ban_time = None
            matches = set()
            processed_text = None
            text_lower = None
            for entry in self.watch_cache[message.guild.id]:

                if entry.match_type == MatchType.regex.value:
                    found = list(entry.compiled.finditer(message.content))
                    if found:
                        delete_message = delete_message or entry.auto_delete
                        if entry.ban != None:
                            if ban_time == None:
                                ban_time = 0
                            ban_time = max(ban_time, entry.ban)
                        watch = await WordWatchWatch.filter(id=entry.id).prefetch_related('group').get()
                        for match in found:
                            matches.add((
                                watch, match.start(0), match.end(0)
                            ))

                elif entry.match_type == MatchType.word.value:
                    if processed_text == None:
                        processed_text = text_preprocess(message.content)
                    found = word_matches(processed_text, entry.compiled)
                    if found:
                        delete_message = delete_message or entry.auto_delete
                        if entry.ban != None:
                            if ban_time == None:
                                ban_time = 0
                            ban_time = max(ban_time, entry.ban)
                        watch = await WordWatchWatch.filter(id=entry.id).prefetch_related('group').get()
                        for match in found:
                            matches.add((
                                watch, match[0], match[1]
                            ))
                
                elif entry.match_type == MatchType.contains.value:
                    if entry.ignore_case and text_lower == None:
                        text_lower = message.content.lower()
                    found = list(find_all_contains(text_lower if entry.ignore_case else message.content, entry.pattern))
                    if found:
                        delete_message = delete_message or entry.auto_delete
                        if entry.ban != None:
                            if ban_time == None:
                                ban_time = 0
                            ban_time = max(ban_time, entry.ban)
                        watch = await WordWatchWatch.filter(id=entry.id).prefetch_related('group').get()
                        for match in found:
                            matches.add((
                                watch, match[0], match[1]
                            ))

            if delete_message:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass # the message may be deleted before we get to it; this shouldn't cause us to not log the message
            
            if ban_time != None:
                try:
                    await message.author.ban(delete_message_days=ban_time)
                except discord.NotFound:
                    pass # user could already be banned

            if matches:
                try:
                    module_settings: WordWatchSettings = await WordWatchSettings.get(guild_id=message.guild.id)
                except DoesNotExist:
                    return
                if module_settings.log_channel == None:
                    return
                    
                log_channel = self.bot.get_channel(module_settings.log_channel)
                if log_channel == None:
                    return
                
                pings = set()
                groups = set()
                for match in matches:
                    if match[0].group != None and match[0].group.id not in groups:
                        groups.add(match[0].group.id)
                        await match[0].group.fetch_related('pings')
                        for ping in match[0].group.pings:
                            pings.add(id2mention(ping.target_id, ping.ping_type))
                
                deduped_patterns = set([o[0].pattern for o in matches])
                pattern_list = commas([str(i) for i in deduped_patterns])
                pattern_list_code = commas([f"`{i}`" for i in deduped_patterns])

                ranges = get_int_ranges(set(
                    (index                       for range_ in
                    (range(match[1], match[2]+1) for match  in matches)
                                                 for index  in range_)
                )) # p y t h o n i c

                message_embed = discord.Embed(
                    color=discord.Color(0xd22513),
                    description='\n'.join([
                        between_segments(message.content, ranges).replace('](', ']\\('),
                        f'[Jump to message]({link_to_message(message)})'
                    ]),
                    timestamp=message.created_at
                )
                message_embed.set_author(
                    name=f'{message.author.name}#{message.author.discriminator} triggered {pattern_list} in #{message.channel.name}',
                    icon_url=message.author.avatar_url
                )
                message_embed.set_footer(text=f'User ID: {message.author.id}', icon_url=message.guild.icon_url)
                message_embed.add_field(name='User', value=id2mention(message.author.id, MentionType.user), inline=True)
                message_embed.add_field(name='Channel', value=id2mention(message.channel.id, MentionType.channel), inline=True)
                message_embed.add_field(name='Deleted', value=bool2str(delete_message, 'Yes', 'No'), inline=True)
                message_embed.add_field(name='When', value=message.created_at.strftime("%d/%m/%y \u200B \u200B %I:%M:%S %p"), inline=True)
                message_embed.add_field(name='Pattern' + pluralize("", "s", len(pattern_list_code)),
                                        value=pattern_list_code, inline=False)

                content = module_settings.header
                if content:
                    template = string.Template(content)
                    content = template.safe_substitute(
                        patterns=pattern_list_code,
                        channel=message.channel.name,
                        channel_reference=id2mention(message.channel.id, MentionType.channel),
                        user=f'{message.author.name}#{message.author.discriminator}',
                        user_ping=id2mention(message.author.id, MentionType.user),
                        user_id=message.author.id
                    )
                else:
                    content = ''
                if pings:
                    if content:
                        content += ' '
                    content += ''.join(pings)
                    if len(content) > 2000:
                        content = content[len(content)-2000:]

                try:
                    await log_channel.send(content=content, embed=message_embed)
                except HTTPException as e:
                    if e.code == 50035: # embed too long
                        # fallback
                        fallback_embed = discord.Embed(
                            color=discord.Color(0xd22513),
                            description=f'[Jump to message]({link_to_message(message)})'
                        )
                        fallback_embed.set_author(
                            name=f'{message.author.name}#{message.author.discriminator} triggered Word Watch in #{message.channel.name}',
                            icon_url=message.author.avatar_url
                        )
                        fallback_embed.set_footer(text=f'Fallback embed • Ping {product_settings.author_name}!')
                        await log_channel.send(content=content, embed=fallback_embed)
        finally:
            end_time = time.time()
            if end_time - start_time >= 1:
                logger.warn(f'message scan took {round(end_time-start_time, 3)} seconds!')
            
    async def scan_loop(self):

        await self.initialized.wait()

        while True:
            item = await self.scan_queue.get()
            if item == None:
                return
            try:
                await self.scan_message(item)
            except Exception as e:
                await self.utils.log_background_error(item.guild, e)
    
    async def close(self):

        await self.scan_queue.put(None)
        await self.scan_task

    def cog_unload():

        self.bot.loop.run_until_complete(self.close())

    async def after_invoke_hook(self, ctx: commands.Context):

        await self.scan_queue.put(ctx.message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author == self.bot.user:
            return
        
        if not isinstance(message.channel, (discord.TextChannel)):
            return

        guild_prefix = await self.bot.command_prefix(self.bot, message)
        if not message.content.startswith(guild_prefix):
            await self.scan_queue.put(message)
    
    @commands.Cog.listener()
    async def on_message_edit(self, old: discord.Message, new: discord.Message):

        if old.content != new.content:
            await self.scan_queue.put(new)

    @commands.command(name='ww.watch')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_watch(self, ctx: commands.Context, watch_settings: str, *patterns: str):

        if len(patterns) == 0:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Please specify some patterns')
            return

        split_settings = [i.split('.') for i in watch_settings.replace(' ', '').split(',')]
        raw_settings = {
            'del': False,
            'cased': False,
            'type': None,
            'ping': None,
            'ban': None
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
        
        if not parsed_settings['cased']:
            patterns = [i.lower() for i in patterns]
        
        if parsed_settings['type'] == MatchType.word and parsed_settings['cased']:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Match type `word` cannot be case sensitive')
            return
        
        if parsed_settings['ping']:
            try:
                group = await WordWatchPingGroup.get(
                    guild_id=ctx.guild.id,
                    name=parsed_settings['ping']
                )
            except DoesNotExist:
                if str2bool(parsed_settings['ping']) == False:
                    group = None
                else:
                    await self.utils.respond(ctx, ResponseLevel.general_error, f'Invalid ping group {parsed_settings["ping"]}')
                    return
        else:
            group = None

        duplicates = 0
        updates = 0
        additions = 0
        db_guild = await Guild.get(id=ctx.guild.id)
        for pattern in patterns:
            try:
                existing = await WordWatchWatch.get(
                    guild=db_guild,
                    pattern=pattern
                ).prefetch_related('guild', 'group')
            except DoesNotExist:
                added = await WordWatchWatch.create(
                    guild=db_guild,
                    pattern=pattern,
                    match_type=parsed_settings['type'].value,
                    group=group,
                    auto_delete=parsed_settings['del'],
                    ignore_case=not parsed_settings['cased'],
                    ban=parsed_settings['ban']
                )
                await self.add_to_cache(added)
                additions += 1
            else:
                # TODO: make this not so terrible
                something_changed = False
                if existing.match_type != parsed_settings['type'].value:
                    existing.match_type = parsed_settings['type'].value
                    something_changed = True
                if existing.group == None:
                    if group != None:
                        existing.group = group
                        something_changed = True
                elif existing.group.name != parsed_settings['ping']:
                    existing.group = group
                    something_changed = True
                if existing.auto_delete != parsed_settings['del']:
                    existing.auto_delete = parsed_settings['del']
                    something_changed = True
                if existing.ignore_case == parsed_settings['cased']:
                    existing.ignore_case = not parsed_settings['cased']
                    something_changed = True
                if existing.ban != parsed_settings['ban']:
                    existing.ban = parsed_settings['ban']
                    something_changed = True
                if something_changed:
                    await existing.save()
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
            message_parts.append(f'added {additions} new word{pluralize("", "s", additions)}')
        if updates:
            message_parts.append(f'updated {updates} existing word{pluralize("", "s", updates)}')
        if duplicates:
            message_parts.append(f'skipped {duplicates} duplicate word{pluralize("", "s", duplicates)}')
        
        await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')

        module_settings: WordWatchSettings = await WordWatchSettings.get(guild_id=ctx.guild.id)
        if module_settings.log_channel == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'WARNING: You have no log channel set, so nothing will be logged!')
    
    async def compute_list_embed(self, ctx: commands.Context, items: List[Tuple[int, WatchCacheEntry]],
                                 page_number: int, page_max: int):

        embed = discord.Embed(
            title=possesivize(ctx.guild.name)
        )
        embed.set_footer(text=f'{page_number+1}/{page_max}')
        for index, item in items:
            watch: WordWatchWatch = await WordWatchWatch.filter(id=item.id).prefetch_related('group').get()
            field_name = f'`{index+1}`: {"word" if watch.match_type == MatchType.word.value else "contains"}'
            name_extras = [i for i in (
                'Autodelete' if watch.auto_delete else None,
                None if watch.ignore_case else 'Cased',
                None if watch.group == None else f'Pings `{watch.group.name}`',
                f'Ban ({item.ban})' if item.ban != None else None
            ) if i != None]
            if name_extras:
                field_name += ' - ' + ', '.join(name_extras)
            embed.add_field(
                name=field_name,
                value='`' + watch.pattern + '`',
                inline=False
            )
        return embed

    @commands.command(name='ww.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list(self, ctx: commands.Context):

        items = list(enumerate(self.watch_cache[ctx.guild.id]))

        if len(items) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No watches found')
            return
        
        await self.utils.list_items(ctx, items, custom_embed=self.compute_list_embed)
    
    @commands.command(name='ww.clear_watches')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_clear_watches(self, ctx: commands.Context):

        if ctx.guild.id in self.watch_cache:
            await WordWatchWatch.filter(guild_id=ctx.guild.id).delete()
            self.watch_cache[ctx.guild.id] = []
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, 'I have no idea where I am')
    
    async def remove_watch(self, ctx: commands.Context, index: int) -> bool:

        try:
            cache_entry: WatchCacheEntry = self.watch_cache[ctx.guild.id][index-1]
        except IndexError:
            return True

        try:
            watch = await WordWatchWatch.get(id=cache_entry.id)
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Index {index} not mapped to a valid ID')
            return False
        
        await watch.delete()
        del self.watch_cache[ctx.guild.id][index-1]
        return False

    @commands.command(name='ww.remove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_remove(self, ctx: commands.Context, *terms: str):

        to_delete = set()
        for term in terms:
            if '-' in term:
                lower, upper = [int(i) for i in term.split('-')]
                to_delete.update(range(lower, upper+1))
            else:
                to_delete.add(int(term))

        indices = sorted(list(to_delete))
        errors = []
        offset = 0
        for index in indices:
            if await self.remove_watch(ctx, index - offset):
                errors.append(index)
            else:
                offset += 1
        
        if errors:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Error removing {"indices" if len(errors) != 1 else "index"} {commas(getrange_s(errors))}')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.qremove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_qremove(self, ctx: commands.Context, *patterns: str):

        errors = []
        for pattern in patterns:

            try:
                watch = await WordWatchWatch.get(guild_id=ctx.guild.id, pattern=pattern)
            except DoesNotExist:
                errors.append(pattern)
            else:
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
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_ignore(self, ctx: commands.Context, *references: str):

        if ctx.guild.id not in self.ignore_cache:
            self.ignore_cache[ctx.guild.id] = set()

        errors = []
        duplicates = 0
        for index, reference in enumerate(references):
            try:
                id = int(reference)
            except ValueError:
                mention_type, id = resolve_mention(reference)
            else:
                mention_type = await self.utils.guess_id(id, ctx.guild)
            if mention_type in [MentionType.channel, MentionType.role, MentionType.user]:
                if id in self.ignore_cache[ctx.guild.id]:
                    duplicates += 1
                else:
                    await WordWatchIgnore.create(guild_id=ctx.guild.id, target_id=id, mention_type=mention_type)
                    self.ignore_cache[ctx.guild.id].add(id)
            else:
                errors.append(index+1)

        if len(errors) > 0:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Error ignoring item{pluralize("", "s", len(errors))} {commas(getrange_s(errors))}')
        else:
            if duplicates > 0:
                await self.utils.respond(ctx, ResponseLevel.success, f'Skipped {duplicates} duplicates')
            else:
                await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.ignored')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_ignored(self, ctx: commands.Context):

        ignored = await WordWatchIgnore.filter(guild_id=ctx.guild.id).all()
        if len(ignored) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'Nothing ignored')
            return
        await self.utils.list_items(ctx,
            [id2mention(ignore.target_id, ignore.mention_type) for ignore in ignored]
        )
    
    @commands.command(name='ww.unignore')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_unignore(self, ctx: commands.Context, *references: str):

        errors = []
        for index, reference in enumerate(references):
            id = mention2id(reference)
            try:
                target_ignore = await WordWatchIgnore.get(target_id=id)
            except DoesNotExist:
                errors.append(index+1)
            else:
                await target_ignore.delete()
                self.ignore_cache[ctx.guild.id].remove(id)

        if len(errors) > 0:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Item{pluralize("", "s", len(errors))} {commas(getrange_s(errors))} not found')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.log')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_log(self, ctx: commands.Context, channel_reference: Optional[str] = None):

        if channel_reference:
            if channel_reference in ['clear', 'reset', 'disable']:
                await WordWatchSettings.filter(guild_id=ctx.guild.id).update(log_channel=None)
            else:
                try:
                    channel_id = int(channel_reference)
                except ValueError:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                await WordWatchSettings.filter(guild_id=ctx.guild.id).update(log_channel=channel_id)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            module_settings: WordWatchSettings = await WordWatchSettings.get(guild_id=ctx.guild.id).only('log_channel')
            if module_settings.log_channel == None:
                response = 'No log channel set'
            else:
                response = id2mention(module_settings.log_channel, MentionType.channel)
            await self.utils.respond(ctx, ResponseLevel.success, response)

    @commands.command(name='ww.header')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_header(self, ctx: commands.Context, *, header_message: Optional[str] = None):

        if header_message:
            if header_message in ['clear', 'reset', 'disable']:
                await WordWatchSettings.filter(guild_id=ctx.guild.id).update(header=None)
            else:
                await WordWatchSettings.filter(guild_id=ctx.guild.id).update(header=header_message)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            module_settings: WordWatchSettings = await WordWatchSettings.get(guild_id=ctx.guild.id)
            await self.utils.respond(ctx, ResponseLevel.success, module_settings.header or 'No header set')
    
    @commands.command(name='ww.add_ping')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_add_ping(self, ctx: commands.Context, group_name: str, *pings: str):

        for not_allowed in string.whitespace + '.':
            if not_allowed in group_name:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Illegal character in group name')

        errors = 0
        duplicates = 0
        additions = 0
        for ping in pings:
            try:
                id = int(ping)
            except ValueError:
                mention_type, id = resolve_mention(ping)
            else:
                mention_type = await self.utils.guess_id(id, ctx.guild)
            
            if mention_type == None:
                errors += 1
            else:
                try:
                    group: WordWatchPingGroup = await WordWatchPingGroup.get(guild_id=ctx.guild.id, name=group_name)
                except DoesNotExist:
                    group: WordWatchPingGroup = await WordWatchPingGroup.create(guild_id=ctx.guild.id, name=group_name)
                pings = await WordWatchPing.filter(group=group).all()
                for db_ping in pings:
                    if db_ping.target_id == id:
                        duplicates += 1
                        break
                else:
                    await WordWatchPing.create(
                        ping_type=mention_type,
                        target_id=id,
                        group=group
                    )
                    additions += 1
        
        if duplicates or errors:
            message_parts = []
            if additions:
                message_parts.append(f'added {additions} new ping{pluralize("", "s", additions)}')
            if errors:
                message_parts.append(f'ignored {errors} malformed ping{pluralize("", "s", errors)}')
            if duplicates:
                message_parts.append(f'skipped {duplicates} duplicate ping{pluralize("", "s", duplicates)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.remove_ping')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_remove_ping(self, ctx: commands.Context, group_name: str, *pings: str):

        try:
            group: WordWatchPingGroup = await WordWatchPingGroup.get(guild_id=ctx.guild.id, name=group_name)
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Group `{group_name}` not found')
            return

        malformed = 0
        to_delete = set()
        for ping in pings:
            try:
                id = int(ping)
            except ValueError:
                _, id = resolve_mention(ping)

            if id == None:
                malformed += 1
            else:
                to_delete.add(id)

        nonexistant = 0
        deletions = 0
        
        db_pings = await WordWatchPing.filter(group=group).all()
        for db_ping in db_pings:
            if db_ping.target_id in to_delete:
                await db_ping.delete()
                deletions += 1
        nonexistant = len(to_delete) - deletions - malformed
        
        if nonexistant or malformed:
            message_parts = []
            if deletions:
                message_parts.append(f'removed {deletions} ping{pluralize("", "s", deletions)}')
            if malformed:
                message_parts.append(f'ignored {malformed} malformed ping{pluralize("", "s", malformed)}')
            if nonexistant:
                message_parts.append(f'skipped {nonexistant} nonexistant ping{pluralize("", "s", nonexistant)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.delete_group')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_delete_group(self, ctx: commands.Context, group_name: str):

        try:
            group: WordWatchPingGroup = await WordWatchPingGroup.get(guild_id=ctx.guild.id, name=group_name)
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Group not found')
        else:
            await group.delete()
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.list_groups')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list_groups(self, ctx: commands.Context):

        groups: List[WordWatchPingGroup] = await WordWatchPingGroup.filter(guild_id=ctx.guild.id).all()
        entries = []
        for group in groups:
            ping_count = await WordWatchPing.filter(group=group).count()
            entries.append(f'{group.name} ({ping_count} ping{pluralize("", "s", ping_count)})')
        if len(entries) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No groups found')
        else:
            await self.utils.list_items(ctx, entries)
    
    @commands.command(name='ww.list_pings')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list_pings(self, ctx: commands.Context, group_name: str):

        pings = await WordWatchPing.filter(group__name=group_name, group__guild_id=ctx.guild.id).all()
        entries = []
        for ping in pings:
            entries.append(id2mention(ping.target_id, ping.ping_type))
        if len(entries) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No pings found')
        else:
            await self.utils.list_items(ctx, entries)

    @commands.command(name='debug.list_cache')
    @is_owner_check()
    async def debug_list_cache(self, ctx: commands.Context, guild_id: int = None):

        if guild_id == None:
            await self.utils.list_items(ctx, [str(i) for i in self.watch_cache])
        else:
            if guild_id in self.watch_cache:
                await self.utils.list_items(ctx, [str(i) for i in self.watch_cache[guild_id]])
            else:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild not found')
    
    @commands.command(name='debug.queue_size')
    @is_owner_check()
    async def debug_queue_size(self, ctx: commands.Context):

        await self.utils.respond(ctx, ResponseLevel.success, str(self.scan_queue._queue.qsize()))

    @commands.command(name='ww.transfer')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_transfer(self, ctx: commands.Context, from_group: str, to_group: str, target_server_id: int):
        
        target = self.bot.get_guild(target_server_id)
        if target is None:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild not found')
            return
        
        if target.owner_id != ctx.author.id:
            try:
                member = await target.fetch_member(ctx.author.id)
            except discord.errors.NotFound as e:
                await self.utils.respond(ctx, ResponseLevel.general_error, "You're not in the target guild")
                return
            
            if member.guild_permissions.administrator != False:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'You need `Administrator` in the target guild')
                return

        try:
            source: WordWatchPingGroup = await WordWatchPingGroup.get(guild_id=ctx.guild.id, name=from_group)
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Group `{from_group}` not found')
            return

        try:
            dest: WordWatchPingGroup = await WordWatchPingGroup.get(guild_id=target_server_id, name=to_group)
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Group `{to_group}` not found')
            return

        await ctx.message.add_reaction('🔄')

        target_guild = await Guild.get(id=target_server_id)

        for watch in await WordWatchWatch.filter(group_id=source.pk).all():
            try:
                existing: WordWatchWatch = await WordWatchWatch.get(
                    guild_id=target_server_id,
                    pattern=watch.pattern
                ).prefetch_related('guild', 'group')
                await existing.delete()
                for i in self.watch_cache[target_server_id]:
                    if i.id == existing.id:
                        self.watch_cache[target_server_id].remove(i)
                        break
                else:
                    print('???')
            except DoesNotExist:
                pass
            added = await WordWatchWatch.create(
                guild=target_guild,
                pattern=watch.pattern,
                match_type=watch.match_type,
                group=dest,
                auto_delete=watch.auto_delete,
                ignore_case=watch.ignore_case,
                ban=watch.ban
            )
            await self.add_to_cache(added)

        await ctx.message.remove_reaction('🔄', self.bot.user)
        await self.utils.respond(ctx, ResponseLevel.success)