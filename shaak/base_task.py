from shaak.consts import TaskInfo
from shaak.custom_bot import CustomBot

class BaseTask:

    meta = TaskInfo(
        name='base_task',
        wait_time=None
    )

    def __init__(self, bot: CustomBot):
        self.bot = bot
    
    async def initialize(self):
        pass

    async def run(self):
        pass