from calendar import *
import datetime
from lightbulb import *

def generate_discord_timestamp(date_time: datetime):
    return timegm(date_time.utcnow().utctimetuple())

def build_progress_bar(progress_state: int, max_state):
    progress_bar = "" #31 long
    for _ in range(progress_state):
        progress_bar = f"{progress_bar}▓"

    for _ in range(max_state - progress_state):
        progress_bar = f"{progress_bar}░"
    return progress_bar

async def add_reaction_to_post(bot_plugin: Plugin, channel_id: str, message_id: str, emoji) -> None :
    await bot_plugin.bot.rest.add_reaction(channel=channel_id, message=message_id, emoji=emoji)