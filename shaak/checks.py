from discord.ext import commands

# from shaak.database import Setting
from shaak.helpers import check_privildged
from shaak.errors import NotAllowed

async def has_privlidged_role(ctx: commands.Context):

    privildged = await check_privildged(ctx.guild, ctx.author)
    if privildged == None:
        return False
    elif privildged == True:
        return True
    elif privildged == False:
        raise NotAllowed()

def has_privlidged_role_check():
    
    return commands.check(has_privlidged_role)
