from discord.ext import commands

class ModuleDisabled(commands.CheckFailure): pass
class NotAllowed(commands.CheckFailure): pass
class InvalidId(Exception): pass
