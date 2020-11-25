# pylint: disable=unsubscriptable-object # pylint/issues/3882
import re
import string
from dataclasses import dataclass
from typing      import Any, Callable, Dict, List, Optional

import discord
import ormar
from discord.errors import HTTPException
from discord.ext    import commands

from shaak.base_module import BaseModule
from shaak.checks      import has_privlidged_role_check
from shaak.consts      import MatchType, ModuleInfo, watch_setting_map
from shaak.database    import WWSetting, WWPing, WWPingGroup, WWWatch, WWIgnore, DBGuild
from shaak.errors      import InvalidId
from shaak.helpers     import (MentionType, between_segments, bool2str, commas,
                               get_int_ranges, getrange_s, id2mention,
                               link_to_message, mention2id, pluralize,
                               resolve_mention)
from shaak.matcher     import pattern_preprocess, text_preprocess, word_matches
from shaak.settings    import product_settings
from shaak.utils       import ResponseLevel, Utils

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
            hash(self.ping_group_id) + \
            hash(self.auto_delete) + \
            hash(self.ignore_case)

class WordWatch(BaseModule):
    
    meta = ModuleInfo(
        name='word_watch',
        settings=WWSetting
    )

    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.watch_cache: Dict[str, WatchCacheEntry] = {}
        self.bot.add_on_error_hooks(self.after_invoke_hook)
    
    async def add_to_cache(self, watch: WWWatch) -> WatchCacheEntry:

        if watch.guild.id not in self.watch_cache:
            self.watch_cache[watch.guild.id] = []
        
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

        self.watch_cache[watch.guild.id].append(cache_entry)
        return cache_entry

    async def initialize(self):
        
        for guild in self.bot.guilds:
            self.watch_cache[guild.id] = []
            await WWSetting.objects.get_or_create(guild=DBGuild(id=guild.id))
        
        for watch in await WWWatch.objects.all():
            if watch.guild.id not in self.watch_cache:
                await watch.delete()
            else:
                await self.add_to_cache(watch)

        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        await self.initialized.wait()
        
        if guild.id not in self.watch_cache:
            self.watch_cache[guild.id] = []
        
        await WWSetting.objects.get_or_create(guild=DBGuild(id=guild.id))
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
        if guild.id in self.watch_cache:
            del self.watch_cache[guild.id]
        
    async def is_id_ignored(self, guild_id, target_id):
        return await WWIgnore.objects.filter(guild__id=guild_id, target_id=target_id).limit(1).count() == 1

    async def scan_message(self, message: discord.Message):

        await self.initialized.wait()
        
        if message.guild is None:
            return
        
        if message.author.bot:
            return
        
        if await self.is_id_ignored(message.guild.id, message.channel.id):
            return

        if message.channel.category_id and await self.is_id_ignored(message.guild.id, message.channel.category_id):
            return
        
        check_member = message.webhook_id == None
        if isinstance(message.author, discord.User):
            try:
                message.author = await message.guild.fetch_member(message.author.id)
            except discord.HTTPException:
                check_member = False

        if check_member:
            for role in message.author.roles:
                if await self.is_id_ignored(message.guild.id, role.id):
                    return
        
        delete_message = False
        matches = set()
        processed_text = None
        for watch in self.watch_cache[message.guild.id]:

            if watch.match_type == MatchType.regex:
                found = list(watch.compiled.finditer(message.content))
                if found:
                    delete_message = delete_message or watch.auto_delete
                    for match in found:
                        matches.add((
                            watch, match.start(0), match.end(0)
                        ))

            elif watch.match_type == MatchType.word:
                if processed_text == None:
                    processed_text = text_preprocess(message.content)
                found = word_matches(processed_text, watch.compiled)
                if found:
                    delete_message = delete_message or watch.auto_delete
                    for match in found:
                        matches.add((
                            watch, match[0], match[1]
                        ))

        if delete_message:
            try:
                await message.delete()
            except discord.NotFound:
                pass # the message may be deleted before we get to it; this shouldn't cause us to not log the message

        if matches:
            module_settings: WWSetting = await WWSetting.objects.get(guild__id=message.guild.id)
            if module_settings.log_channel == None:
                return
                
            log_channel = self.bot.get_channel(module_settings.log_channel)
            if log_channel == None:
                return
            
            ping_groups = []
            for match in matches:
                if match[0].ping_group_id not in ping_groups:
                    ping_groups.append(match[0].ping_group_id)
            str_pings = set()
            for group in ping_groups:
                pings = await WWPing.objects.filter(group=group).all()
                for ping in pings:
                    str_pings.add(id2mention(ping.target_id, ping.ping_type))

            deduped_patterns = set([o[0].pattern for o in matches])
            pattern_list = commas([str(i) for i in deduped_patterns])
            pattern_list_code = commas([f"`{i}`" for i in deduped_patterns])

            raw_segments = sorted(list(set(
                [index                     for range_ in
                [range(match[1], match[2]+1) for match  in matches]
                                           for index  in range_]
            ))) # p y t h o n i c
            ranges = get_int_ranges(raw_segments)

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
            if str_pings:
                if content:
                    content += ' '
                content += ''.join(str_pings)
                if len(content) > 2000:
                    content = content[len(content)-2000:]

            try:
                await log_channel.send(content=content, embed=message_embed)
            except HTTPException as e:
                if e.code == 50035:
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

    async def after_invoke_hook(self, ctx: commands.Context):

        await self.scan_message(ctx.message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author == self.bot.user:
            return
        
        if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
            return

        guild_prefix = await self.bot.command_prefix(self.bot, message)
        if not message.content.startswith(guild_prefix):
            await self.scan_message(message)
    
    @commands.Cog.listener()
    async def on_message_edit(self, old: discord.Message, new: discord.Message):

        if old.content != new.content:
            await self.on_message(new)

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
                    name=parsed_settings['ping']
                )
            except ormar.NoMatch:
                await self.utils.respond(ctx, ResponseLevel.general_error, f'Invalid ping group {parsed_settings["ping"]}')
                return
        else:
            ping_group = None

        duplicates = 0
        updates = 0
        additions = 0
        db_guild = await DBGuild.objects.get(id=ctx.guild.id)
        for pattern in patterns:
            try:
                existing = await WWWatch.objects.get(
                    guild=db_guild,
                    pattern=pattern
                )
            except ormar.NoMatch:
                added = await WWWatch.objects.create(
                    guild=db_guild,
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
            message_parts.append(f'added {additions} new word{pluralize("", "s", additions)}')
        if updates:
            message_parts.append(f'updated {updates} existing word{pluralize("", "s", updates)}')
        if duplicates:
            message_parts.append(f'ignored {duplicates} duplicate word{pluralize("", "s", duplicates)}')
        
        await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')

        module_settings: WWSetting = await WWSetting.objects.get(guild__id=ctx.guild.id)
        if module_settings.log_channel == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'WARNING: You have no log channel set, so nothing will be logged!')
    
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
        ], escape=True)
    
    @commands.command(name='ww.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list(self, ctx: commands.Context):

        await self.list_words(ctx)
    
    @commands.command(name='ww.clear_watches')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_clear_watches(self, ctx: commands.Context):

        if ctx.guild.id in self.watch_cache:
            to_delete = await WWWatch.objects.filter(guild__id=ctx.guild.id).all()
            [await watch.delete() for watch in to_delete]
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
            watch = await WWWatch.objects.get(id=cache_entry.id)
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Index {index} not mapped to a valid ID')
            return False
        
        await watch.delete()
        del self.watch_cache[ctx.guild.id][index-1]
        return False

    @commands.command(name='ww.remove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_remove(self, ctx: commands.Context, *ranges: str):

        to_delete = set()
        for range_ in ranges:
            if '-' in range_:
                lower, upper = [int(i) for i in range_.split('-')]
                to_delete.update(range(lower, upper+1))
            else:
                to_delete.add(int(range_))

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
                watch = await WWWatch.objects.get(guild__id=ctx.guild.id, pattern=pattern)
            except ormar.NoMatch:
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

        db_guild: DBGuild = await DBGuild.objects.get(id=ctx.guild.id)

        errors = []
        duplicates = 0
        for index, reference in enumerate(references):
            try:
                id = int(reference)
            except ValueError:
                mention_type, id = resolve_mention(reference)
            else:
                mention_type = await self.utils.guess_id(id, ctx.guild)
            if mention_type in [MentionType.channel, MentionType.role]:
                if await self.is_id_ignored(ctx.guild.id, id):
                    duplicates += 1
                else:
                    await WWIgnore.objects.create(guild=db_guild, target_id=id, mention_type=mention_type)
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
        
        ignored = await WWIgnore.objects.filter(guild__id=ctx.guild.id).all()
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
            try:
                id = mention2id(reference, MentionType.channel)
            except InvalidId:
                id = mention2id(reference, MentionType.role)
            try:
                target_ignore = await WWIgnore.objects.get(target_id=id)
            except ormar.NoMatch:
                errors.append(index+1)
            else:
                await target_ignore.delete()

        if len(errors) > 0:
            await self.utils.respond(ctx, ResponseLevel.general_error,
                f'Item{pluralize("", "s", len(errors))} {commas(getrange_s(errors))} not found')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.log')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_log(self, ctx: commands.Context, channel_reference: Optional[str] = None):

        module_settings: WWSetting = await WWSetting.objects.get(guild__id=ctx.guild.id)
        if channel_reference:
            if channel_reference in ['clear', 'reset', 'disable']:
                await module_settings.update(log_channel=None)
            else:
                try:
                    channel_id = int(channel_reference)
                except ValueError:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                await module_settings.update(log_channel=channel_id)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            if module_settings.log_channel == None:
                response = 'No log channel set'
            else:
                response = id2mention(module_settings.log_channel, MentionType.channel)
            await self.utils.respond(ctx, ResponseLevel.success, response)

    @commands.command(name='ww.header')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_header(self, ctx: commands.Context, *, header_message: Optional[str] = None):

        module_settings: WWSetting = await WWSetting.objects.get(guild__id=ctx.guild.id)
        if header_message:
            if header_message in ['clear', 'reset', 'disable']:
                await module_settings.update(header=None)
            else:
                await module_settings.update(header=header_message)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
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
                    group: WWPingGroup = await WWPingGroup.objects.get(guild__id=ctx.guild.id, name=group_name)
                except ormar.NoMatch:
                    db_guild: DBGuild = await DBGuild.objects.get(id=ctx.guild.id)
                    group: WWPingGroup = await WWPingGroup.objects.create(guild=db_guild, name=group_name)
                pings = await WWPing.objects.filter(group=group).all()
                for db_ping in pings:
                    if db_ping.target_id == id:
                        duplicates += 1
                        break
                else:
                    await WWPing.objects.create(
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
                message_parts.append(f'skipped {errors} malformed ping{pluralize("", "s", errors)}')
            if duplicates:
                message_parts.append(f'ignored {duplicates} duplicate ping{pluralize("", "s", duplicates)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.remove_ping')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_remove_ping(self, ctx: commands.Context, group_name: str, *pings: str):

        try:
            group: WWPingGroup = await WWPingGroup.objects.get(guild__id=ctx.guild.id, name=group_name)
        except ormar.NoMatch:
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
        
        db_pings = await WWPing.objects.filter(group=group).all()
        for db_ping in db_pings:
            if db_ping.target_id in to_delete:
                await db_ping.delete()
                deletions += 1
        nonexistant = deletions - malformed
        
        if nonexistant or malformed:
            message_parts = []
            if deletions:
                message_parts.append(f'removed {deletions} ping{pluralize("", "s", deletions)}')
            if malformed:
                message_parts.append(f'skipped {malformed} malformed ping{pluralize("", "s", malformed)}')
            if nonexistant:
                message_parts.append(f'ignored {nonexistant} nonexistant ping{pluralize("", "s", nonexistant)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.delete_group')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_delete_group(self, ctx: commands.Context, group_name: str):

        try:
            group: WWPingGroup = await WWPingGroup.objects.get(guild__id=ctx.guild.id, name=group_name)
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Group not found')
        else:
            await group.delete()
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.list_groups')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list_groups(self, ctx: commands.Context):

        groups: List[WWPingGroup] = await WWPingGroup.objects.filter(guild__id=ctx.guild.id).all()
        entries = []
        for group in groups:
            ping_count = await WWPing.objects.filter(group=group).count()
            entries.append(f'{group.name} ({ping_count} ping{pluralize("", "s", ping_count)})')
        if len(entries) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No groups found')
        else:
            await self.utils.list_items(ctx, entries)
    
    @commands.command(name='ww.list_pings')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def ww_list_pings(self, ctx: commands.Context, group_name: str):

        pings = await WWPing.objects.filter(group__name=group_name).all()
        entries = []
        for ping in pings:
            entries.append(id2mention(ping.target_id, ping.ping_type))
        if len(entries) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No pings found')
        else:
            await self.utils.list_items(ctx, entries)
