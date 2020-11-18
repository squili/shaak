from discord.ext import commands

from shaak.database import Setting
from shaak.helpers import check_privildged
from shaak.errors import NotAllowed

def has_privlidged_role():
    
    async def predicate(ctx: commands.Context):
        privildged = check_privildged(ctx.guild, ctx.author)
        if privildged == None:
            return False
        elif privildged == True:
            return True
        elif privildged == False:
            raise NotAllowed()

    return commands.check(predicate)
