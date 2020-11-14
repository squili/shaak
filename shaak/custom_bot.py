from discord.ext import commands
from shaak.consts import ResponseLevel
from shaak.base_module import ModuleDisabled

class CustomBot(commands.Bot):
    
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        
        if not hasattr(self, 'utils'):
            self.utils = self.get_cog('Utils')
        
        if isinstance(error, commands.CheckAnyFailure):
            error = error.errors[0]
        
        if isinstance(error, (ModuleDisabled, commands.CommandNotFound)):
            return
        elif isinstance(error, (commands.MissingPermissions, commands.MissingRole)):
            await self.utils.respond(ctx, ResponseLevel.forbidden, 'You do not have permission to run this command')
        else:
            await self.utils.respond(ctx, ResponseLevel.internal_error, f'Unhandled error of type {type(error).__name__}. Check the console!')
            raise error