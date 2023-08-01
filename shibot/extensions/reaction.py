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
import pytz, time
from typing import TypedDict, Dict, List, Iterable
from pytz import timezone
import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from shibot import GUILD_ID, BOT_USER_ID
from hikari.api.special_endpoints import MessageActionRowBuilder

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

log = logging.getLogger(__name__)

sched = AsyncIOScheduler()

##########################################
##               CRON JOBS              ##
##########################################

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def check_old_events() -> None:
    await on_startup()
    
    to_remove = [
        event[0]
        for event in tracked_channels.items()
        if event[1].event_timeout - timedelta(minutes=5) < datetime.now().replace(tzinfo=pytz.UTC)
    ]
    
    for key in to_remove:
        tracked_channels.pop(key)
        await mod_plugin.bot.rest.create_message(key, f"<#{key}> | Event signup period has ended.")

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def update_roster() -> None:
    await on_startup()
    
    for forum_event in tracked_channels.values():
        iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=forum_event.channelid, message=forum_event.messageid, emoji=emoji_dict.get("🔔")["emoji"])
        users = [str(user.id) for user in iterator if user.id != BOT_USER_ID]
        interested_users.update({forum_event.channelid: users})
        for emoji in emoji_dict.values() :
            if emoji["emoji"] == "🔔":
                continue
            user_mentions = await fetch_emoji_info(forum_event, emoji)
            forum_event.roster_cache.update({str(emoji["id"]): user_mentions})

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def backup_tracked_files() -> None:
    await on_startup()
    
    try :
        await build_json(TRACKING_JSON_FILE, tracked_channels)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    try :
        await build_json(INTERESTED_JSON_FILE,interested_users)
    except FileNotFoundError:
        log.error(f"Interested File Doesn't Exist {INTERESTED_JSON_FILE}")

##########################################
##            REACTION EVENTS           ##
##########################################

@mod_plugin.listener(hikari.ReactionEvent)
async def print_reaction(event: hikari.ReactionEvent) -> None:
    global log, red_x_emoji, tracked_channels
    log.info("*** | Start Handle Reaction Event | ***")
    red_x_emoji_link = str(red_x_emoji["emoji"])
    if not isinstance(event, hikari.ReactionAddEvent) and not isinstance(event, hikari.ReactionDeleteEvent) :
        log.info("*** | Finish Handle Reaction Event | Not Add/Delete | ***")
        return
    
    # Ignore bot reactions
    if event.user_id == BOT_USER_ID :
        log.info("*** | Finish Handle Reaction Event | Bot User | ***")
        return
    
    if event.emoji_name != "🔔" :
        log.info("*** | Finish Handle Reaction Event | Non-Interested Reaction | ***")
        return
    
    if str(event.channel_id) not in tracked_channels:
        log.info("*** | Finish Handle Reaction Event | Not a Tracked Channel | ***")
        return;
    
    tracked_event = tracked_channels.get(event.channel_id)
    
    if tracked_event and str(tracked_event.message.id) != str(event.message_id) :
        log.info("*** | Finish Handle Reaction Event | Not a Tracked Message | ***")
        return;
    
    if isinstance(event, hikari.ReactionAddEvent):
        await handle_reaction_add_event(event, red_x_emoji_link)
    elif isinstance(event,hikari.ReactionDeleteEvent):
        await handle_reaction_delete_event(event, red_x_emoji_link)
    else: 
        log.error(f"Unhandled Event Type: {event}")
        
    log.info("*** | Finish Handle Reaction Event | ***")
    
    return

async def handle_reaction_delete_event(event, red_x_emoji_link):
    global log
    log.info("*** | Start Handle Reaction Delete Event | ***")
    
    messages = await mod_plugin.bot.rest.fetch_messages(event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if red_x_emoji_link in message.content and f"{event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
    await mod_plugin.bot.rest.create_message(event.channel_id, f" {red_x_emoji_link} | <@{event.user_id}> | No longer interested in attending the event.")
    
    log.info("*** | Finish Handle Reaction Delete Event | ***")

async def handle_reaction_add_event(event, red_x_emoji_link):
    global log, interested_users
    log.info("*** | Start Handle Reaction Add Event | ***")
    
    messages = await mod_plugin.bot.rest.fetch_messages(event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if "✅" in message.content and f"{event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
        if red_x_emoji_link in message.content and f"{event.user_id}" in message.content :
            await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
    
    interested_users.get(str(event.channel_id)).append(str(event.user_id))
    await mod_plugin.bot.rest.create_message(event.channel_id, f" ✅ | <@{event.user_id}> | Interested in attending.")
    
    log.info("*** | Finish Handle Reaction Add Event | ***")

##########################################
##            TRACKING METHOD           ##
##########################################

async def add_reactions_to_post(ctx, message_id, response_message, response, tracking,reaction,verify,roster):
    global log
    log.info(f"*** | Start Adding Reactions To Post | Message: {message_id} | ***")
    timestamp = generate_discord_timestamp(datetime.now())

    if ctx.options.custom:
        reaction = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
        await response.edit(embed)
        
        log.info(f"*** | Finish Adding Reactions To Post | Custom Post | Message: {message_id} | ***")
        return reaction
    
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=ctx.channel_id, message=message_id, emoji=emoji_dict.get("🔔")["emoji"])
    already_added = next(user for user in iterator if user.id == BOT_USER_ID) is not None
    
    if already_added and not ctx.options.force_emojis:
        reaction = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
        await response.edit(embed)
        log.info(f"*** | Finish Adding Reactions To Post | Already Added | Message: {message_id} | ***")
        return reaction

    reaction_progress = 0
    current_progress = 0

    await add_reaction(channel_id=ctx.channel_id, message_id=message_id, emoji_name="Interested", emoji_id="🔔", emoji="🔔")
    await add_reaction(channel_id=ctx.channel_id, message_id=message_id, emoji_name="New", emoji_id="🆕", emoji="🆕")
    await add_reaction(channel_id=ctx.channel_id, message_id=message_id, emoji_name="Filler", emoji_id="⭐", emoji="⭐")
    
    current_progress = 3

    emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
    for emoji in emojis :
        emoji_id = str(emoji.id)
        if emoji_id in EMOJI_IDS :
            saved_emoji = DefaultEmoji(name=str(emoji.name), id=emoji_id, emoji=emoji)
            emoji_dict.update({emoji_id: saved_emoji})

    reaction_progress = int((current_progress * PROGRESS_BAR_LENGTH) / (len(emoji_dict.values())+3))
    reaction = [red_x_emoji["emoji"],build_progress_bar(reaction_progress, PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
    await response.edit(embed)

    for emoji_id in EMOJI_IDS :
        current_progress+= 1
        emoji = emoji_dict.get(emoji_id)
        await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=message_id, emoji=emoji["emoji"])
        reaction_progress = (current_progress * PROGRESS_BAR_LENGTH) / (len(emoji_dict.values())+3)
        reaction = [red_x_emoji["emoji"],build_progress_bar(int(reaction_progress),PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
        await response.edit(embed)
    log.info(f"*** | Finish Adding Reactions To Post | Message: {message_id} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Post | Update Reaction Stage | Message: {message_id} | ***")
    reaction = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Post | Update Reaction Stage | Message: {message_id} | ***")
    
    return reaction

async def updateInterestedUsers(channel_id: str, message_id: str, response, tracking, reaction, verify, roster, response_message):
    global log
    log.info(f"*** | Start Update Insterested Users For Post | Message: {message_id} | ***")
    
    timestamp = generate_discord_timestamp(datetime.now())
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=channel_id, message=message_id, emoji=emoji_dict.get("🔔")["emoji"])
    users = [str(user.id) for user in iterator if user.id != BOT_USER_ID]
    interested_users.update({channel_id: users})
    
    log.info(f"*** | Finish Update Insterested Users For Post | Message: {message_id} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Post | Update Verify Stage | Message: {message_id} | ***")
    
    verify = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
    await response.edit(embed)
    
    log.info(f"*** | Finish Building Progress Bar For Post | Update Verify Stage | Message: {message_id} | ***")
    
    return verify

async def build_tracking_info(ctx, channel_id, message_id, event_id, response_message, response, tracking, reaction, verify, roster):
    global log
    log.info(f"*** | Start Building Tracking Info For Post | Message: {message_id} | ***")
    timestamp = generate_discord_timestamp(datetime.now())
    event_time = (datetime.now() + timedelta(days=ctx.options.timeout)).replace(tzinfo=pytz.UTC)
    
    event = None
    timeout = event_time
    if ctx.options.event_id :
        event = await mod_plugin.bot.rest.fetch_scheduled_event(ctx.guild_id,event_id)
        event_time = event.start_time.replace(tzinfo=pytz.UTC) - SERVER_TIME_OFFSET
    
    roster_cache = {}
    verified_users = []
    mains = {}
    
    forum_event = ForumEvent(f"{channel_id}", message_id, ctx.options.custom, roster_cache, verified_users, event_time, timeout, mains)
    
    tracked_channels.update({f"{ctx.channel_id}": forum_event})
    log.info(f"*** | Finish Building Tracking Info For Post | Message: {message_id} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Post | Update Tracking Stage | Message: {message_id} | ***")
    tracking = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Post | Update Tracking Stage | Message: {message_id} | ***")
    
    return forum_event, tracking

async def update_roster(buildCache, forum_event: ForumEvent, response, tracking, reaction, verify, roster, response_message) -> None:
    global log
    log.info(f"*** | Start Building Roster For Post | Update Roster Stage | Message: {forum_event.messageid} | ***")
    timestamp = generate_discord_timestamp(datetime.now())
    roster_progress = 0
    current_progress = 0
    
    if not buildCache:
        roster = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
        discord_timestamp = generate_discord_timestamp(datetime.now())
        embed = await print_tracking_stages(discord_timestamp, tracking,reaction,verify,roster,response_message)
        await response.edit(embed)
        return roster
    
    for emoji in emoji_dict.values() :
        current_progress+= 1
        if emoji["emoji"] == "🔔":
            continue
        user_mentions = await fetch_emoji_info(forum_event, emoji)
        forum_event.roster_cache.update({str(emoji["id"]): user_mentions})
        roster_progress = (current_progress * PROGRESS_BAR_LENGTH) / len(emoji_dict.values())
        roster = [red_x_emoji["emoji"],build_progress_bar(int(roster_progress),PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,verify,roster,response_message)
        await response.edit(embed)
    log.info(f"*** | Finish Building Roster For Post | Update Roster Stage | Message: {forum_event.messageid} | ***")
    
    log.info(f"*** | Start Building Progress Bar Post | Update Roster Stage | Message: {forum_event.messageid} | ***")
    roster = ["✅",build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    discord_timestamp = generate_discord_timestamp(datetime.now())
    embed = await print_tracking_stages(discord_timestamp, tracking,reaction,verify,roster,response_message)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar Post | Update Roster Stage | Message: {forum_event.messageid} | ***")
    
    return roster

##########################################
##            SHARED METHODS            ##
##########################################

async def add_reaction(channel_id: str, message_id: str, emoji_name, emoji_id, emoji) -> None :
    global log
    log.info(f"*** | Start Adding Reaction To Post | Message: {message_id} | Emoji: {emoji_name} | ***")
    await mod_plugin.bot.rest.add_reaction(channel=channel_id, message=message_id, emoji=emoji)
    saved_emoji = DefaultEmoji(name=emoji_name, id=emoji_id, emoji=emoji)
    emoji_dict.update({emoji_id: saved_emoji})
    log.info(f"*** | Finish Adding Reaction To Post | Message: {message_id} | Emoji: {emoji_name} | ***")

async def print_tracking_stages(timestamp, tracking_stage, reaction_stage, interested_stage, roster_cache_stage, message: str) -> hikari.Embed:
    global log
    total_progress_amount = calc_total_progress(tracking_stage, reaction_stage, interested_stage, roster_cache_stage)
    
    embed = hikari.Embed(title="Registering Event For Tracking...",color="#949fe6")
    
    embed.add_field(f"{tracking_stage[0]} | Building Tracking Info...", tracking_stage[1])
    progress_state = 0 + (3 if tracking_stage[0] == "✅" else 0)

    embed.add_field(f"{reaction_stage[0]} | Adding Emojis to Message...", reaction_stage[1])
    progress_state += 7 if reaction_stage[0] == "✅" else 0
    
    embed.add_field(f"{interested_stage[0]} | Verifying Already Interested Users...", interested_stage[1])
    progress_state += 2 if interested_stage[0] == "✅" else 0
    
    embed.add_field(f"{roster_cache_stage[0]} | Building Roster Cache...", roster_cache_stage[1])
    progress_state += 13 if roster_cache_stage[0] == "✅" else 0
    if roster_cache_stage[0] != "✅":
        emoji_link = red_x_emoji["emoji"]
        embed.add_field(f"{emoji_link} | Working on Registering Event for Tracking.", message)
    else: 
        embed.add_field("✅ | Finished Registering Event for Tracking.", message)
    
    progress_bar = build_progress_bar(progress_state=total_progress_amount, max_state=PROGRESS_BAR_LENGTH)
    
    embed.add_field(progress_bar, f"Last update processed <t:{timestamp}:R>")

    return embed

async def generate_buttons_for_main(forum_event: ForumEvent, user_id: str, bot: lightbulb.BotApp, valid_mains) -> Iterable[MessageActionRowBuilder]:
    global log
    log.info(f"*** | Start Generating Buttons For Main Embed | Message: {forum_event.messageid} | ***")

    rows: List[MessageActionRowBuilder] = []

    row = bot.rest.build_message_action_row()

    for i in range(len(valid_mains)):
        if i % 3 == 0 and i != 0:
            rows.append(row)
            row = bot.rest.build_message_action_row()

        row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            list(valid_mains)[i]["name"],
            emoji=list(valid_mains)[i]["emoji"],
            label=list(valid_mains)[i]["name"].upper().replace("_", " "),
        )

    rows.append(row)
    log.info(f"*** | Finish Generating Buttons For Embed | Message: {forum_event.messageid} | ***")

    return rows

def generate_discord_timestamp(date_time: datetime):
    return calendar.timegm(date_time.utcnow().utctimetuple())

async def createEmbedForReaction(ctx: lightbulb.Context, forum_event: ForumEvent) -> hikari.Embed:
    global log
    log.info(f"*** | Start Generating Embed For Roster | Message: {forum_event.messageid} | ***")
    embed = hikari.Embed(title="PRE-ROSTER",color= "#949fe6")
    
    if not forum_event.roster_cache :
        embed.add_field("Roster not generated yet for post", "Please contact dev if this persists.")
        log.info(f"*** | Finish Generating Embed For Roster | Message: {forum_event.messageid} | ***")
        return embed
        
    for emoji in emoji_dict.values() :
        if emoji["emoji"] == "🔔":
            continue
        user_mentions = forum_event.roster_cache.get(str(emoji["id"]))
        emoji_link = emoji["emoji"]
        reaction_name = emoji["name"].upper().replace("_", " ")
        embed.add_field(f"{emoji_link} | {reaction_name}", user_mentions)
    embed.set_footer("Message Mods/Admins if you need more help")
    log.info(f"*** | Finish Generating Embed For Roster | Message: {forum_event.messageid} | ***")
    return embed

##########################################
##             INFO FETCHING            ##
##########################################

async def fetch_emoji_info(forum_event: ForumEvent, emoji):
    global log
    emoji_name = emoji["name"]
    log.info(f"*** | Start Fetching Emoji Info For Post | Message: {forum_event.messageid} | Emoji: {emoji_name} | ***")
    
    emoji_link = emoji["emoji"]
    users = await mod_plugin.bot.rest.fetch_reactions_for_emoji(forum_event.channelid, message=forum_event.messageid, emoji=emoji_link)
    user_mentions = ""
    for user in users :
        if str(user.id) not in interested_users[forum_event.channelid] :
            continue
        
        is_main = False
        
        if forum_event.mains and forum_event.mains.get(str(user.id)):
            is_main = forum_event.mains.get(str(user.id))["id"] == str(emoji["id"])

        if user_mentions == "" :
            user_mentions = user.mention
        else :
            user_mentions = f"{user_mentions}, {user.mention}"
        
        if is_main:
            user_mentions = f"{user_mentions}*"
            
    log.info(f"*** | Finish Fetching Emoji Info For Post | Message: {forum_event.messageid} | Emoji: {emoji_name} | ***")

    return user_mentions if user_mentions != "" else "N/A"

##########################################
##              UPDATE DATA             ##
##########################################

async def update_specific_roster(ctx: lightbulb.UserContext, forum_event: ForumEvent) -> None: 
    global log
    log.info(f"*** | Start Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
    
    red_x = red_x_emoji["emoji"]
    timestamp = generate_discord_timestamp(datetime.now())
    roster_progress = 0
    current_progress = 0
    
    embed = hikari.Embed(title="Updating Roster State...",color="#949fe6")
    progress = build_progress_bar(roster_progress,PROGRESS_BAR_LENGTH)
    embed.add_field(f"{red_x} | Roster Loading...", progress)
    response = await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=forum_event.channelid, message=forum_event.messageid, emoji=emoji_dict.get("🔔")["emoji"])
    users = [user for user in iterator if user.id != BOT_USER_ID]
    interested_users.update({forum_event.channelid: users})

    valid_user = next(user for user in iterator if str(user.username) == str(ctx.author.username) )
    
    if valid_user is None:
        embed = hikari.Embed(title="Error",color="#949fe6",description=f"{red_x} | Not Marked Interested")
        await response.edit(embed)
        log.info(f"*** | Finish Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
        return None
    
    for emoji in emoji_dict.values() :
        current_progress += 1
        if emoji["emoji"] == "🔔":
            continue
        user_mentions = await fetch_emoji_info(forum_event, emoji)
        forum_event.roster_cache.update({str(emoji["id"]): user_mentions})
        roster_progress = (current_progress * PROGRESS_BAR_LENGTH) / len(emoji_dict.values())
        progress = build_progress_bar(int(roster_progress),PROGRESS_BAR_LENGTH)
        embed = hikari.Embed(title="Updating Roster State...",color="#949fe6")
        embed.add_field(f"{red_x} | Roster Loading...", progress)
        await response.edit(embed)
        
    log.info(f"*** | Finish Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Main Command | Message: {forum_event.messageid} | ***")
    progress = build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Updating Roster State...",color="#949fe6")
    embed.add_field("✅ | Roster Loading...", progress)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Main Command | Message: {forum_event.messageid} | ***")
    
    return response

async def handle_response_main(bot: lightbulb.BotApp,author: hikari.User,message: hikari.Message, list, forum_event: ForumEvent, footer, ) -> None:
    global log
    with bot.stream(hikari.InteractionCreateEvent, 120).filter(

                lambda e: (isinstance(e.interaction, hikari.ComponentInteraction) and e.interaction.user == author and e.interaction.message == message)
            ) as stream:
        async for event in stream:
            log.info(f"*** | Start Handling Response For Main Command | Message: {forum_event.messageid} | User: {author.username} | ***")
            cid = event.interaction.custom_id
            main: MainEmoji = None
            main_emoji: DefaultEmoji = None
            for emoji in emoji_dict.values() :
                if cid == emoji["name"] :
                    main =MainEmoji(name=emoji["name"],id=str(emoji["id"]))
                    main_emoji = emoji
                    break;

            emoji_link = emoji["emoji"]
            main_name = main["name"].upper().replace("_", " ")
            
            user_mentions = await mod_plugin.bot.rest.fetch_reactions_for_emoji(forum_event.channelid, message=forum_event.messageid, emoji=emoji_link)
            
            if user_mention := [
                user for user in user_mentions if user.id == author.id
            ]:
                forum_event.mains.update({str(author.id): main}, )
                embed = hikari.Embed(title=main_name,description=f"Main set to {emoji_link} {main_name}",)
            else:
                embed = hikari.Embed(title="Invalid Main Attempted",description=f"Please react first | {emoji_link} {main_name}.",color="#880808")

            if footer : embed.set_footer(footer)

            try:
                await event.interaction.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE,embed=embed)
            except hikari.NotFoundError:
                await event.interaction.edit_initial_response(embed=embed,)

            log.info(f"*** | Finish Handling Response For Main Command | Message: {forum_event.messageid} | User: {author.username} | ***")

    try:
        await message.edit(components=[])
    except hikari.NotFoundError:
        return

##########################################
##             PROGRESS BARS            ##
##########################################

def calc_total_progress(tracking_stage, reaction_stage, interested_stage, roster_cache_stage):
    tracking_progress_amount = int(tracking_stage[1].count('▓'))
    reaction_progress_amount = int(reaction_stage[1].count('▓'))
    interested_progress_amount = int(interested_stage[1].count('▓'))
    roster_progress_amount = int(roster_cache_stage[1].count('▓'))
    return int(
        (
            (
                tracking_progress_amount
                + reaction_progress_amount
                + interested_progress_amount
                + roster_progress_amount
            )
            / (PROGRESS_BAR_LENGTH * 4)
        )
        * PROGRESS_BAR_LENGTH
    )

def build_progress_bar(progress_state: int, max_state):
    progress_bar = "" #31 long
    for _ in range(progress_state):
        progress_bar = f"{progress_bar}▓"

    for _ in range(max_state - progress_state):
        progress_bar = f"{progress_bar}░"
    return progress_bar

##########################################
##              VALIDATION              ##
##########################################

async def validate_authorized_user(ctx) -> bool:
    global log
    log.info(f"*** | Start Validating Authorized User | Message: {ctx.options.message_id} | User: {ctx.author} | ***")
    now = datetime.now(pytz.timezone('America/New_York')).strftime("%m/%d/%Y %I:%M:%S %p")
    messages = await mod_plugin.bot.rest.fetch_messages(channel=ctx.channel_id)
    messages[-1].author.id
    authorized_users = tracked_channels.get(ctx.channel_id).authorized_users if tracked_channels.get(ctx.channel_id) else []
    if not authorized_users :
        authorized_users.append(messages[-1].author.id)
    
    #TODO: Add override for mods
    if ctx.author.id not in authorized_users:
        embed = hikari.Embed(title="UNAUTHORIZED USER",color="#880808")
        embed.set_footer("Unable to execute command")
        await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
        log.error(f"{now} | Unauthorized Command Attempt |  {ctx.author} | {ctx.get_channel().name} | Attempted to execute /{ctx.command.name}")
        return False
    else :
        log.info(f"{now} | Authorized Command Attempt | {ctx.author} | {ctx.get_channel().name} | Executed /{ctx.command.name}")
    log.info(f"*** | Finish Validating Authorized User | Message: {ctx.options.message_id} | User: {ctx.author} | ***")
    
    return True

##########################################
##             BUILD OUTPUT             ##
##########################################

async def build_json(filename, structure):
    global log
    log.info("*** | Start Building Json Backup | ***")
    json_output = jsonpickle.encode(structure)
    log.info("*** | Finish Building Json Backup | ***")
    
    log.info("*** | Start Saving Json Backup | ***")
    with open(filename, "w") as outfile:
        outfile.write(json_output)
    log.info("*** | Finish Saving Json Backup | ***")
    
    return

def load_tracked_file_json_backup(filename):
    global log, tracked_channels
    log.info("*** | Start Loading Tracked Json Backup| ***")
    with open(filename, 'r') as infile:
        tracked_channels = jsonpickle.decode(infile.read())
    log.info("*** | Start Finish Tracked Json Backup | ***")

def load_interested_file_json_backup(filename):
    global log, interested_users
    log.info("*** | Start Loading Interested Json Backup| ***")
    with open(filename, 'r') as infile:
        interested_users = jsonpickle.decode(infile.read())
    log.info("*** | Start Finish Interested Json Backup | ***")

##########################################
##               COMMANDS               ##
##########################################

@mod_plugin.command
@lightbulb.option(
    "custom",
    "Enables custom reactions",
    type=bool,
    required=False,
    default=False
)
@lightbulb.option(
    "build_cache",
    "Instantly build roster cache",
    type=bool,
    required=False,
    default=False
)
@lightbulb.option(
    "event_id",
    "Associates this post with an event.",
    type=str,
    required=False,
)
@lightbulb.option(
    "message_id",
    "Associates this post with a specific message.",
    type=str,
    required=True,
)
@lightbulb.option(
    "timeout",
    "number of day(s) before a channel is removed from the tracked list",
    type=int,
    required=False,
    default=7
)
@lightbulb.option(
    "force_emojis",
    "force emojis to be added to the post, even if the bot has already previously added them",
    type=bool,
    required=False,
    default=False
)
@lightbulb.command("track", "Begin tracking the associated post")
@lightbulb.implements(lightbulb.SlashCommand)
async def track_post(ctx: lightbulb.Context) -> None:
    global red_x_emoji
    await on_startup()
    authorized = await validate_authorized_user(ctx)
    
    if authorized == False:
        return
    
    message_id : str = ctx.options.message_id
    if "https://discord.com/" in message_id :
        message_id = message_id.split("/")[-1]
        
    event_id : str = ctx.options.event_id
    if event_id and "https://discord.com/" in event_id :
        event_id = event_id.split("/")[-1]
    
    response_message = f"Tracking https://discord.com/channels/{ctx.guild_id}/{ctx.channel_id}/{message_id}"
    if ctx.options.event_id :
        response_message = f"{response_message} for https://discord.com/events/{ctx.guild_id}/{event_id}"
    
    discord_timestamp = generate_discord_timestamp(datetime.now())
    tracking = [red_x_emoji["emoji"],build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    reaction = [red_x_emoji["emoji"],build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    verify = [red_x_emoji["emoji"],build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    roster = [red_x_emoji["emoji"],build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(discord_timestamp,tracking,reaction,verify,roster,response_message)
    response = await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    
    discord_timestamp = generate_discord_timestamp(datetime.now())
    tracking_event, tracking = await build_tracking_info(ctx, ctx.get_channel().id, message_id, event_id, response_message,response,tracking,reaction,verify,roster)
    
    reaction = await add_reactions_to_post(ctx, message_id, response_message, response, tracking,reaction,verify,roster)
    
    verify = await updateInterestedUsers(ctx.channel_id, message_id, response, tracking,reaction,verify,roster, response_message)
    
    roster = await update_roster(ctx.options.build_cache, tracking_event, response, tracking,reaction,verify,roster,response_message)
    
    now = datetime.now(pytz.timezone('America/New_York')).strftime("%m/%d/%Y %I:%M:%S %p")
    log.info(f"*** | Authorized Command Complete | {ctx.author} | {ctx.get_channel().name} | Executed /{ctx.command.name} | ***")

@mod_plugin.command
@lightbulb.option(
    "force_reload",
    "Force reload of roster, only necessary if you've reacted to your main role in the last 5 minutes",
    type=bool,
    required=False,
    default=False
)
@lightbulb.command("roster", "Displays everyone's playable roles based on their reactions to the post above.")
@lightbulb.implements(lightbulb.SlashCommand)
async def check_roster(ctx: lightbulb.Context) -> None:
    global tracked_channels
    await on_startup()
    
    event = tracked_channels.get(f"{ctx.channel_id}")
    
    if not event :
        await ctx.respond("Post is not currently being tracked.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    if ctx.options.force_reload :
        response = await update_specific_roster(ctx, event)
        
        if response is None :
            return
    
    response = await ctx.respond(hikari.Embed(title="Fetching Pre-Roster..."),flags=hikari.MessageFlag.EPHEMERAL)
    embed = await createEmbedForReaction(ctx, event)
    await response.edit(embed=embed)

@mod_plugin.command
@lightbulb.command("main", "Allows a user to set a main role based on their reactions. Disabled for Custom Events.")
@lightbulb.implements(lightbulb.SlashCommand)
async def set_main(ctx:lightbulb.Context) -> None:
    await on_startup()
        
    event = tracked_channels.get(f"{ctx.channel_id}")
    if not event or event.custom == True :
        log.error(f"Failed to load {ctx.channel_id}, not in tracked events.")
        embed = hikari.Embed(title="INVALID CHANNEL",color="#880808")
        embed.set_footer("This channel has not been added to tracked events.")
        await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
        return;
        
    valid_mains = [emoji for emoji in emoji_dict.values() if emoji["id"] in EMOJI_IDS]
    rows = await generate_buttons_for_main(event, str(ctx.author.id), ctx.bot, valid_mains)
    response = await ctx.respond(hikari.Embed(title="Pick a Main"),components=rows,flags=hikari.MessageFlag.EPHEMERAL)
    message = await response.message()
    footer = None
    try:
        await handle_response_main(ctx.bot, ctx.author, message, valid_mains, event, footer)
    except lightbulb.CommandInvocationError:
        return

@mod_plugin.command
@lightbulb.command("load", "Initial Startup")
@lightbulb.implements(lightbulb.SlashCommand)
async def load(ctx:lightbulb.Context) -> None:
    log.info("*** | Start Initializing Mod | ***")
    success = await on_startup()

    if success:
        embed = hikari.Embed(title="Finished Initializing Mod",color="#949fe6")
    else:
        embed = hikari.Embed(title="Mod Already Initialized...",color="#949fe6")
    
    await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    log.info("*** | Finish Initializing Mod | ***")

@mod_plugin.command
@lightbulb.command("backup", "Forced Backup")
@lightbulb.implements(lightbulb.SlashCommand)
async def load(ctx:lightbulb.Context) -> None:
    log.info("*** | Start Backup | ***")
    success = await backup_tracked_files()

    embed = hikari.Embed(title="Finished Backing Up",color="#949fe6")
    await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    log.info("*** | Finished Backup | ***")

@mod_plugin.command
@lightbulb.option(
    "ephemeral",
    "Forces the release notes to be invisible",
    type=bool,
    required=False,
    default=True
)
@lightbulb.command("release_notes", "Release Notes (v1.0.0)")
@lightbulb.implements(lightbulb.SlashCommand)
async def load(ctx:lightbulb.Context) -> None:
    log.info("*** | Start Release Notes | ***")
    embed = hikari.Embed(title="Release Notes", color="#00ffff", url="https://github.com/twardle/DiscordBot_Hikari/blob/master")
    embed.add_field("Safe Reboot","*Shibot will now remember things, even after unexpected naps!*")
    embed.add_field("Performance Enhancements","*Shibot's zoomies are off the charts thanks to being a bit more lazy!*")
    embed.add_field("Caching Cleanup","*Shibot now only remembers the important things...*")
    embed.add_field("Logging Handling","*Shibot sometimes makes mistakes, and that's ok.*")
    embed.set_thumbnail("https://github.com/twardle/DiscordBot_Hikari/blob/master/Shiba_logo.png?raw=true")
    embed.set_footer("Shibot v1.0.0")
    
    if ctx.options.ephemeral :
        await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    else :
        await ctx.respond(embed)
    log.info("*** | Finished Release Notes | ***")

##########################################
##               START UP               ##
##########################################

async def on_startup() :
    global log, reloaded, red_x_emoji, emoji_dict, tracked_channels, sched
    
    if reloaded == 1:
        return False
    
    log = logging.getLogger(__name__)
    info_handler = logging.FileHandler('log/shibot.log')
    info_handler.setLevel(logging.INFO)
    log.addHandler(info_handler)
    error_handler = logging.FileHandler('log/shibot_error.log')
    error_handler.setLevel(logging.ERROR)
    log.addHandler(error_handler)
    
    try :
        load_tracked_file_json_backup(TRACKING_JSON_FILE)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    try :
        load_interested_file_json_backup(INTERESTED_JSON_FILE)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
    for emoji in emojis :
        if str(emoji.id) == RED_X_EMOJI_ID :
            red_x_emoji = DefaultEmoji(name=emoji.name, id=emoji.id, emoji=emoji)
            break;
    
    saved_emoji = DefaultEmoji(name="Interested", id="🔔", emoji="🔔")
    emoji_dict.update({"🔔":saved_emoji})
    saved_emoji = DefaultEmoji(name="New", id="🆕", emoji="🆕")
    emoji_dict.update({"🆕":saved_emoji})
    saved_emoji = DefaultEmoji(name="Filler", id="⭐", emoji="⭐")
    emoji_dict.update({"⭐":saved_emoji})
    
    emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
    for emoji in emojis :
        emoji_id = str(emoji.id)
        if emoji_id in EMOJI_IDS :
            saved_emoji = DefaultEmoji(name=str(emoji.name), id=emoji_id, emoji=emoji)
            emoji_dict.update({emoji_id: saved_emoji})
    
    sched.start()
    
    reloaded = 1
    return True
    
def load(bot: lightbulb.BotApp) -> None:    
    jsonpickle.set_encoder_options('simplejson', use_decimal=True, indent=4)
    jsonpickle.set_decoder_options('simplejson', use_decimal=True)
    jsonpickle.set_preferred_backend('simplejson')
    bot.add_plugin(mod_plugin)