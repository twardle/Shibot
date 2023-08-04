# TODO: Add /Special Roles command
# TODO: Add /Authorize command
# TODO: Order Users by Signup Order
# FEATURE REQUEST: Sample Roster
# FEATURE REQUEST: DM Sign ups before event
# FEATURE REQUEST: Low Priority (Not Filler)
# FEATURE REQUEST: Setup Database handling

import logging
import json
import jsonpickle as jsonpickle
import simplejson
import lightbulb
import hikari
import pytz
from typing import TypedDict, Dict, List, Iterable
from pytz import timezone
import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from shibot import GUILD_ID, BOT_USER_ID, DEV_BOT_USER_ID, __version__
from hikari.api.special_endpoints import MessageActionRowBuilder
import logging

##########################################
##                LOGGER                ##
##########################################

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

##########################################
##               CLASSES                ##
##########################################

class DefaultEmoji(TypedDict):
    name: str
    id: int
    emoji: hikari.Emoji
    
class MainEmoji(TypedDict):
    name: str
    id: int

class ForumEvent:
    def __init__(self, channelid: str, messageid: str, custom: bool, roster_cache: Dict[str,str], verified_users: List[str], event_timeout: datetime, tracking_timeout: datetime, mains: Dict[str,MainEmoji]):
        self.channelid = channelid
        self.messageid = messageid
        self.custom = custom
        self.roster_cache = roster_cache
        self.authorized_users = verified_users
        self.event_timeout = event_timeout
        self.tracking_timeout = tracking_timeout
        self.mains = mains
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)

##########################################
##                CONSTS                ##
##########################################

MAX_LOADING_PERCENT = 100
TRACKING_JSON_FILE = "backup/tracking_backup.json"
INTERESTED_JSON_FILE = "backup/interested_backup.json"
SERVER_TIME_OFFSET = timedelta(hours=4)
EMOJI_IDS = [
    "1108505145697898647", # Quick Heal
    "1108505147149131776", # Alac Heal
    "1108505150827544696", # Quick DPS
    "1108505144737402901", # Alac DPS
    "1108505149154009220", # Condi DPS
    "1108505148201902182", # Power DPS
    ]
RED_X_EMOJI_ID = "1108922427221745724"
PROGRESS_BAR_LENGTH = 25

##########################################
##               VARIABLES              ##
##########################################

tracked_channels: Dict[str, ForumEvent] = {}
emoji_dict = {}
interested_users = {}
red_x_emoji : DefaultEmoji = None
mod_plugin = lightbulb.Plugin("Reaction")
reloaded = 0

##########################################
##                 LOGGER               ##
##########################################

# sched = AsyncIOScheduler()

##########################################
##               CRON JOBS              ##
##########################################

# @sched.scheduled_job(CronTrigger(minute="*/30"))
# async def check_old_events() -> None:
    
#     to_remove = [
#         event[0]
#         for event in tracked_channels.items()
#         if event[1].event_timeout - timedelta(minutes=30) < datetime.now().replace(tzinfo=pytz.UTC)
#     ]
    
#     for key in to_remove:
#         tracked_channels.pop(key)
#         await mod_plugin.bot.rest.create_message(key, f"<#{key}> | Event signup period has ended.")

##########################################
##            REACTION EVENTS           ##
##########################################

@mod_plugin.listener(hikari.ReactionEvent)
async def print_reaction(event: hikari.ReactionEvent) -> None:
    global red_x_emoji, tracked_channels
    log.info("*** | Start Handle Reaction Event | ***")
    if not isinstance(event, hikari.ReactionAddEvent) and not isinstance(event, hikari.ReactionDeleteEvent) :
        log.info("*** | Finish Handle Reaction Event | Not Add/Delete | ***")
        return
    
    if str(event.channel_id) not in tracked_channels:
        log.info("*** | Finish Handle Reaction Event | Not a Tracked Channel | ***")
        return;
    
    # Ignore bot reactions
    if event.user_id == BOT_USER_ID or event.user_id == DEV_BOT_USER_ID :
        log.info("*** | Finish Handle Reaction Event | Bot User | ***")
        return
    
    tracked_event = tracked_channels.get(event.channel_id)
    
    if tracked_event and str(tracked_event.message.id) != str(event.message_id) :
        log.info("*** | Finish Handle Reaction Event | Not a Tracked Message | ***")
        return;
    
    red_x_emoji_link = str(red_x_emoji["emoji"])
    
    if event.emoji_name == "🔔" and isinstance(event, hikari.ReactionAddEvent):
        await handle_interested_reaction_add_event(event, red_x_emoji_link)
    elif event.emoji_name == "🔔" and isinstance(event,hikari.ReactionDeleteEvent):
        await handle_interested_reaction_delete_event(event, red_x_emoji_link)
    else: 
        event_string = str(event).encode("utf-8")
        log.error(f"Unhandled Event Type: {event_string}")
        
    log.info("*** | Finish Handle Reaction Event | ***")
    
    return

async def handle_interested_reaction_delete_event(forum_event, red_x_emoji_link):
    global log
    log.info("*** | Start Handle Reaction Delete Event | ***")
    
    messages = await mod_plugin.bot.rest.fetch_messages(forum_event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if red_x_emoji_link in message.content and f"{forum_event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=forum_event.channel_id)
    await mod_plugin.bot.rest.create_message(forum_event.channel_id, f" {red_x_emoji_link} | <@{forum_event.user_id}> | No longer interested in attending the event.")
    
    log.info("*** | Finish Handle Reaction Delete Event | ***")

async def handle_interested_reaction_add_event(forum_event, red_x_emoji_link):
    global interested_users
    log.info("*** | Start Handle Reaction Add Event | ***")
    
    messages = await mod_plugin.bot.rest.fetch_messages(forum_event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if "✅" in message.content and f"{forum_event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=forum_event.channel_id)
        if red_x_emoji_link in message.content and f"{forum_event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=forum_event.channel_id)
    
    if interested_users.get(str(forum_event.channel_id)) :
        interested_users.get(str(forum_event.channel_id)).append(str(forum_event.user_id))
    else :
        interested_users.update({forum_event.channel_id: str(forum_event.user_id)})
    
    await mod_plugin.bot.rest.create_message(forum_event.channel_id, f" ✅ | <@{forum_event.user_id}> | Interested in attending.")
    
    log.info("*** | Finish Handle Reaction Add Event | ***")
    
def load(bot: lightbulb.BotApp) -> None:    
    jsonpickle.set_encoder_options('simplejson', use_decimal=True, indent=4)
    jsonpickle.set_decoder_options('simplejson', use_decimal=True)
    jsonpickle.set_preferred_backend('simplejson')
    bot.add_plugin(mod_plugin)