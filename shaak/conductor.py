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
import time
from dataclasses import dataclass
from typing      import List, Coroutine

from discord.ext import commands

from shaak.base_task  import BaseTask
from shaak.custom_bot import CustomBot
from shaak.consts     import TaskInfo

@dataclass
class TaskStore:
    name: str
    wait: float
    exec: Coroutine

class Conductor(commands.Cog):

    def __init__(self, bot: CustomBot, loop: asyncio.BaseEventLoop = None):
        self.bot = bot
        self.new_tasks: List[BaseTask] = []
        self.loop: asyncio.BaseEventLoop = loop or asyncio.get_event_loop()
    
    def load_task(self, cls):

        if not hasattr(cls, 'meta') or not isinstance(cls.meta, TaskInfo):
            print(f'Invalid task metadata: {cls.__name__}')
            return
        
        self.new_tasks.append(cls(self.bot))
    
    async def task_callback(self, task: TaskStore):
        wait_until = time.time() + task.wait
        await task.exec()
        await asyncio.sleep(wait_until - time.time())
        self.loop.create_task(self.task_callback(task))
    
    async def process_new_tasks(self):
        print('Conductor started')
        for task in self.new_tasks:
            await task.initialize()
            self.loop.create_task(
                self.task_callback(
                    TaskStore(
                        name=task.meta.name,
                        wait=task.meta.wait_time,
                        exec=task.run
                    )
                )
            )
    
    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.manager_ready.wait()
        await self.process_new_tasks()