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

from shaak.consts     import TaskInfo
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