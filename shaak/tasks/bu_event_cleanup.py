'''
Shaak Discord moderation bot
Copyright (C) 2020 Squili

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

from datetime import datetime, timedelta

from shaak.consts    import TaskInfo
from shaak.base_task import BaseTask
from shaak.models    import BanUtilBanEvent, BanUtilCrossbanEvent

class BUEventCleanupTask(BaseTask):

    meta = TaskInfo(
        name='bu_event_cleanup_task',
        wait_time=60 * 60 * 24
    )

    async def run(self):

        cutoff = datetime.now() - timedelta(days=30)
        await BanUtilBanEvent     .filter(timestamp__lt=cutoff).delete()
        await BanUtilCrossbanEvent.filter(timestamp__lt=cutoff).delete()