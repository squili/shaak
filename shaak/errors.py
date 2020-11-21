from discord.ext import commands

class ModuleDisabled(commands.CheckFailure): pass
class NotAllowed(commands.CheckFailure): pass
class InvalidId(Exception):
    def __init__(self, message='Invalid Id'):
        self.message = message
    def __str__(self):
        return self.message
