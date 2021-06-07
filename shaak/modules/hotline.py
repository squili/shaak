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
from string import Template
from typing import Optional

import discord
from discord.ext import commands

from shaak.base_module import BaseModule
from shaak.models      import HotlineSettings, HotlineTemplate
from shaak.consts      import ResponseLevel, ModuleInfo, MentionType
from shaak.checks      import has_privlidged_role_check
from shaak.helpers     import id2mention, duration_parse

class Hotline(BaseModule):
    
    meta = ModuleInfo(
        name='hotline',
        settings=HotlineSettings
    )

    @commands.command('hl.role')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def hl_role(self, ctx: commands.Context, role_raw: Optional[str]):
        
        if role_raw == None:
            module_settings: HotlineSettings = await HotlineSettings.filter(guild_id=ctx.guild.id).only('mute_role').get()
            if module_settings.mute_role == None:
                await self.utils.respond(ctx, ResponseLevel.success, 'No mute role set')
            else:
                await self.utils.respond(ctx, ResponseLevel.success, id2mention(module_settings.mute_role, MentionType.role))
        else:
            role = await commands.RoleConverter.convert(ctx, role_raw)
            if role == None:
                if role_raw in ['clear', 'unset', 'disable']:
                    await HotlineSettings.filter(guild_id=ctx.guild.id).update(mute_role=None)
                    await self.utils.respond(ctx, ResponseLevel.success)
                else:
                    await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid role')
            else:
                await HotlineSettings.filter(guild_id=ctx.guild.id).update(mute_role=role.id)
                await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command('hl.add')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def hl_add(self, ctx: commands.Context, name: str, *, text: str):

        template = await HotlineTemplate.filter(name=name, guild_id=ctx.guild.id).get_or_none()
        if template == None:
            await HotlineTemplate.create(name=name, text=' '.join(text), guild_id=ctx.guild.id)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            template.text = ' '.join(text)
            await template.save()
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command('hl.remove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def hl_remove(self, ctx: commands.Context, name: str):
        
        await HotlineTemplate.filter(name=name, guild_id=ctx.guild.id).delete()
        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command('hl.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def hl_list(self, ctx: commands.Context):
        
        names = []
        for i in await HotlineTemplate.filter(guild_id=ctx.guild.id).all():
            names.append(i.name)
        if len(names) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No entries')
        else:
            await self.utils.list_items(ctx, names)

    @commands.command('hl.lecture')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def hl_bonk(self, ctx: commands.Context, target: discord.Member, text: str, length: Optional[str]):

        pattern = await HotlineTemplate.filter(name=text, guild_id=ctx.guild.id).get_or_none()
        if pattern == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Template not found')

        if length:
            mute_length = duration_parse(length)
            if mute_length == None:
                await self.utils.respond(ctx, ResponseLevel.success, 'Invalid duration')
                return
            module_settings: HotlineSettings = await HotlineSettings.filter(guild_id=ctx.guild.id).only('mute_role').get()
            if module_settings.mute_role != None:
                await target.add_roles(discord.Object(module_settings.mute_role), reason=f'Hotline triggered by {ctx.author.id}')
                def callback():
                    asyncio.create_task(target.remove_roles(discord.Object(module_settings.mute_role), reason=f'Hotline expired'))
                asyncio.get_running_loop().call_later(mute_length, callback)
        
        template = Template(pattern.text)
        text = template.safe_substitute(
            username=target.name
        )

        dms = target.dm_channel
        if target.dm_channel == None:
            dms = await target.create_dm()
        await dms.send(embed=discord.Embed(
            title=f'Alert from {ctx.guild.name}',
            description=text
        ))

        await self.utils.respond(ctx, ResponseLevel.success)