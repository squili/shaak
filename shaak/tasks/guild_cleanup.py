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

from datetime import datetime, timedelta

from shaak.consts    import TaskInfo
from shaak.base_task import BaseTask
from shaak.models    import Guild

class GuildCleanupTask(BaseTask):

    meta = TaskInfo(
        name='guild_cleanup_task',
        wait_time=60 * 60 * 24
    )

    async def run(self):

        now = datetime.now()
        guild_ids = set()
        for guild in self.bot.guilds:
            guild_ids.add(guild.id)
        for db_guild in await Guild.all():
            if db_guild.id in guild_ids:
                if db_guild.delete_at != None:
                    await db_guild.update(delete_at=None)
            else:
                if db_guild.delete_at == None:
                    await db_guild.update(delete_at=datetime.now() + timedelta(days=90))
            if db_guild.delete_at != None and db_guild.delete_at < now:
                await db_guild.delete()