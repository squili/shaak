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

import psutil

from shaak.base_task import BaseTask
from shaak.consts    import TaskInfo, cpu_usage_stat, mem_usage_stat

class PerformanceMetrics(BaseTask):

    meta = TaskInfo(
        name='performance_metrics',
        wait_time=60 * 60
    )

    async def initialize(self):
        self.process = psutil.Process()
        self.process.cpu_percent()

    async def run(self):
        cpu_usage_stat.push(self.process.cpu_percent())
        mem_usage_stat.push(self.process.memory_info().rss)