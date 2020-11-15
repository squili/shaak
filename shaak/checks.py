from discord.ext import commands

from shaak.database import Setting

def has_privlidged_role():
    
    async def predicate(ctx: commands.Context):
        server_settings: Setting = Setting.objects.get(server_id=ctx.guild.id)

        if server_settings.authenticated_role == None:
            return False

        for role in ctx.author.roles:
            if role.id == server_settings.authenticated_role:
                return True
        else:
            raise commands.MissingRole(server_settings.authenticated_role)

    return commands.check(predicate)
