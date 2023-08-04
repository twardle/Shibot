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

sched = AsyncIOScheduler()

##########################################
##               CRON JOBS              ##
##########################################

@sched.scheduled_job(CronTrigger(minute="*/30"))
async def check_old_events() -> None:
    
    to_remove = [
        event[0]
        for event in tracked_channels.items()
        if event[1].event_timeout - timedelta(minutes=30) < datetime.now().replace(tzinfo=pytz.UTC)
    ]
    
    for key in to_remove:
        tracked_channels.pop(key)
        await mod_plugin.bot.rest.create_message(key, f"<#{key}> | Event signup period has ended.")

# @sched.scheduled_job(CronTrigger(minute="*/5"))
# async def update_rosters_cache_job() -> None:
#     log.info("*** | Start Update Roster Cache Job | ***")
    
#     for forum_event in tracked_channels.values():
#         for emoji in emoji_dict.values() :
#             if emoji["emoji"] == "🔔":
#                 continue
#             user_mentions = await fetch_emoji_info(forum_event, emoji)
#             forum_event.roster_cache.update({str(emoji["id"]): user_mentions})

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def backup_tracked_files() -> None:
    log.info("*** | Start Building Json Backup | ***")
    
    try :
        await build_json(TRACKING_JSON_FILE, tracked_channels)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    try :
        await build_json(INTERESTED_JSON_FILE,interested_users)
    except FileNotFoundError:
        log.error(f"Interested File Doesn't Exist {INTERESTED_JSON_FILE}")
    log.info("*** | Finish Building Json Backup | ***")

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

##########################################
##            SHARED METHODS            ##
##########################################

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
        if str(user.id) not in interested_users[str(forum_event.channelid)] :
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
    
    if ctx :
        embed = hikari.Embed(title="Updating Roster State...",color="#949fe6")
        progress = build_progress_bar(roster_progress,PROGRESS_BAR_LENGTH)
        embed.add_field(f"{red_x} | Roster Loading...", progress)
        response = await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=forum_event.channelid, message=forum_event.messageid, emoji=emoji_dict.get("🔔")["emoji"])
    users = [str(user.id) for user in iterator if user.id != BOT_USER_ID and user.id == DEV_BOT_USER_ID]
    
    interested_users.update({forum_event.channelid: users})
    
    for emoji in emoji_dict.values() :
        current_progress += 1
        if emoji["emoji"] == "🔔":
            continue
        user_mentions = await fetch_emoji_info(forum_event, emoji)
        forum_event.roster_cache.update({str(emoji["id"]): user_mentions})
        
        if ctx:
            roster_progress = (current_progress * PROGRESS_BAR_LENGTH) / len(emoji_dict.values())
            progress = build_progress_bar(int(roster_progress),PROGRESS_BAR_LENGTH)
            embed = hikari.Embed(title="Updating Roster State...",color="#949fe6")
            embed.add_field(f"{red_x} | Roster Loading...", progress)
            await response.edit(embed)
        
    log.info(f"*** | Finish Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
    
    if ctx:
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
##             BUILD OUTPUT             ##
##########################################

async def build_json(filename, structure):
    global log
    json_output = jsonpickle.encode(structure)
    with open(filename, "w") as outfile:
        outfile.write(json_output)
    
    return

def load_tracked_file_json_backup(filename):
    global tracked_channels
    log.info("*** | Loading Tracked Json Backup| ***")
    with open(filename, 'r') as infile:
        tracked_channels = jsonpickle.decode(infile.read())

def load_interested_file_json_backup(filename):
    global interested_users
    log.info("*** | Loading Interested Json Backup| ***")
    with open(filename, 'r') as infile:
        interested_users = jsonpickle.decode(infile.read())

##########################################
##               COMMANDS               ##
##########################################



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
    await on_startup(ctx)
    
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
    await on_startup(ctx)
        
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
@lightbulb.command("init", "Initial Startup")
@lightbulb.implements(lightbulb.SlashCommand)
async def init(ctx:lightbulb.Context) -> None:
    success = await on_startup(ctx)

    if success:
        embed = hikari.Embed(title="Finished Initializing Mod",color="#949fe6")
    else:
        embed = hikari.Embed(title="Mod Already Initialized...",color="#949fe6")
    
    await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)

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
@lightbulb.command("release_notes", "Release Notes")
@lightbulb.implements(lightbulb.SlashCommand)
async def load(ctx:lightbulb.Context) -> None:
    log.info("*** | Start Release Notes | ***")
    embed = hikari.Embed(title="Release Notes", color="#00ffff", url="https://github.com/twardle/DiscordBot_Hikari/blob/master")
    embed.add_field("Safe Reboot","*Shibot will now remember things, even after unexpected naps!*")
    embed.add_field("Performance Enhancements","*Shibot's zoomies are off the charts thanks to being a bit more lazy!*")
    embed.add_field("Caching Cleanup","*Shibot now only remembers the important things...*")
    embed.add_field("Logging Handling","*Shibot sometimes makes mistakes, and that's ok.*")
    embed.set_thumbnail("https://github.com/twardle/DiscordBot_Hikari/blob/master/Shiba_logo.png?raw=true")
    embed.set_footer(f"Shibot {__version__}")
    
    if ctx.options.ephemeral :
        await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    else :
        await ctx.respond(embed)
    log.info("*** | Finished Release Notes | ***")

##########################################
##               START UP               ##
##########################################

async def on_startup(ctx:lightbulb.Context) :
    global reloaded, sched
    log.info("*** | Initializing Bot | ***")
    
    if reloaded == 1:
        log.info("*** | Bot Initialization Already Complete | ***")
        return False
    
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    response = await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    
    await fetch_red_x_emoji(response)
    
    log.info("*** | Loading Backups | ***")
    
    await load_backup_files(response)
    
    log.info("*** | Building Emoji Dictionary | ***")
    
    await build_emoji_dict(response)
    
    log.info("*** | Fetching Newly Interested Users | ***")
    
    await fetch_newly_interested_users(response)
    
    log.info("*** | Rebuilding Roster Cache | ***")
    
    await update_roster_cache(response)
    
    log.info("*** | Starting Cron Jobs | ***")
    
    sched.start()
    
    current_percent = 100
    adjusted_progress = (current_percent * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"✅ | Roster Loading...", progress)
    await response.edit(embed)
    
    log.info("*** | Finished Initializing Bot | ***")
    
    reloaded = 1
    return True

async def update_roster_cache(response):
    global red_x_emoji, tracked_channels
    red_x = red_x_emoji["emoji"]
    
    start_percent = 35
    max_gained_percent=45
    current_iteration=1
    
    for forum_event in tracked_channels.values():
        current_progress = ((current_iteration-1) * max_gained_percent)/len(tracked_channels)
        adjusted_progress = ((start_percent + current_progress) * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
        progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
        embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
        embed.add_field(f"{red_x} | Updating Roster Cache... ({current_iteration}/{len(tracked_channels)})", progress)
        await response.edit(embed)
        current_iteration += 1
        
        await update_specific_roster(None, forum_event=forum_event)
    
    current_progress = 80
    adjusted_progress = (current_progress * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"{red_x} | Starting Job Schedules...", progress)
    await response.edit(embed)
    

async def fetch_newly_interested_users(response):
    global red_x_emoji
    red_x = red_x_emoji["emoji"]
    
    for forum_event in tracked_channels.values():
        try :
            reactions = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=forum_event.channelid, message=forum_event.messageid, emoji=emoji_dict.get("🔔")["emoji"])
        except hikari.errors.NotFoundError:
            log.warn("*** | Start Update Roster Job | Channel/Message Doesn't Exist | Channel: {forum_event.channelid} | Message: {forum_event.messageid} | ***")
        users = [str(user.id) for user in reactions if user.id != BOT_USER_ID and user.id != DEV_BOT_USER_ID]
        interested_users.update({forum_event.channelid: users})
    
    current_percent = 35
    adjusted_progress = (current_percent * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"{red_x} | Updating Roster Cache...", progress)
    await response.edit(embed)

async def build_emoji_dict(response):
    global red_x_emoji
    red_x = red_x_emoji["emoji"]
    
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
    
    current_percent = 25
    adjusted_progress = (current_percent * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"{red_x} | Fetching Interested Users...", progress)
    await response.edit(embed)

async def load_backup_files(response):
    global red_x_emoji
    red_x = red_x_emoji["emoji"]
    
    try :
        load_tracked_file_json_backup(TRACKING_JSON_FILE)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    try :
        load_interested_file_json_backup(INTERESTED_JSON_FILE)
    except FileNotFoundError:
        log.error(f"Tracking File Doesn't Exist {TRACKING_JSON_FILE}")
    
    current_percent = 15
    adjusted_progress = (current_percent * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"{red_x} | Emoji Dictionary Loading...", progress)
    await response.edit(embed)

async def fetch_red_x_emoji(response):
    global red_x_emoji
    
    emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
    for emoji in emojis :
        if str(emoji.id) == RED_X_EMOJI_ID :
            red_x_emoji = DefaultEmoji(name=emoji.name, id=emoji.id, emoji=emoji)
            break;
        
    red_x = red_x_emoji["emoji"]
    
    current_percent = 5
    adjusted_progress = (current_percent * PROGRESS_BAR_LENGTH) / MAX_LOADING_PERCENT
    progress = build_progress_bar(int(adjusted_progress),PROGRESS_BAR_LENGTH)
    embed = hikari.Embed(title="Initializing Mod...",color="#949fe6")
    embed.add_field(f"{red_x} | Importing Backup Files...", progress)
    await response.edit(embed)
    
def load(bot: lightbulb.BotApp) -> None:    
    jsonpickle.set_encoder_options('simplejson', use_decimal=True, indent=4)
    jsonpickle.set_decoder_options('simplejson', use_decimal=True)
    jsonpickle.set_preferred_backend('simplejson')
    bot.add_plugin(mod_plugin)