from discord.ext import commands
from shaak.database import get_setting

def has_privlidged_role():
    
    async def predicate(ctx: commands.Context):
        authenticated_role_id = await get_setting(ctx.guild.id, 'authenticated_role', False)
        
        if authenticated_role_id == None:
            return False

        for role in ctx.author.roles:
            if role.id == authenticated_role_id:
                return True
        else:
            raise commands.MissingRole(authenticated_role_id)

    return commands.check(predicate)