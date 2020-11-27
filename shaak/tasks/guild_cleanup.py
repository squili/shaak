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
                    await db_guild.update(delete_at=datetime.now() + timedelta(weeks=1))
            if db_guild.delete_at != None and db_guild.delete_at < now:
                await db_guild.delete()