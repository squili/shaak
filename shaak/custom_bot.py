import asyncio

import discord
from discord.ext import commands

from shaak.errors import ModuleDisabled
from shaak.consts import ResponseLevel

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
            error = error.errors[0]
        
        if isinstance(error, (ModuleDisabled, commands.CommandNotFound)):
            return
        elif isinstance(error, (commands.MissingPermissions, commands.MissingRole)):
            await self.utils.respond(ctx, ResponseLevel.forbidden, 'You do not have permission to run this command')
        elif isinstance(error, discord.HTTPException) and error.code == 10008:
            print('yet another damn command interrupted before i could finish with it')
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Unhandled error of type {type(error).__name__}. Check the console!')
            raise error