# TODO: Add /Main Command for individual users
# TODO: Add Redundancies to prevent people tracking others events
# TODO: Add /Special Roles command
# TODO: Order Users by Signup Order
# FEATURE REQUEST: Sample Roster
# FEATURE REQUEST: DM Sign ups before event
# FEATURE REQUEST: 

import lightbulb
import hikari
import pytz
from typing import TypedDict, Dict
from pytz import timezone
import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from shibot import GUILD_ID, BOT_USER_ID

class DefaultEmoji(TypedDict):
    name: str
    id: int
    emoji: hikari.Emoji

class ForumEvent:
    def __init__(self, channel: hikari.GuildChannel, message: hikari.Message, event: hikari.GuildEvent, custom: bool, roster_cache: Dict[str,str], event_timeout: datetime, tracking_timeout: datetime):
        self.channel = channel
        self.message = message
        self.event = event
        self.custom = custom
        self.event_timeout = event_timeout
        self.tracking_timeout = tracking_timeout
        self.roster_cache = roster_cache
    
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
red_x_emoji : DefaultEmoji = None

tracked_channel_ids = {}
emoji_dict = {}
interested_users = {}
mod_plugin = lightbulb.Plugin("Reaction")

sched = AsyncIOScheduler()
sched.start()

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def check_old_events() -> None:
    to_remove = [
        event[0]
        for event in tracked_channel_ids.items()
        if event[1].event_timeout - timedelta(minutes=5) < datetime.now().replace(tzinfo=pytz.UTC)
    ]
    
    for key in to_remove:
        tracked_channel_ids.pop(key)
        await mod_plugin.bot.rest.create_message(key, f"<#{key}> | Event signup period has ended.")

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def update_roster() -> None:
    
    for forum_event in tracked_channel_ids.values():
        await updateInterestedUsers(channel_id=forum_event.channel.id, message_id=forum_event.message.id)
        for emoji in emoji_dict.values() :
            if emoji["emoji"] == "🔔":
                continue
            user_mentions = await fetch_emoji_info(forum_event, emoji)
            forum_event.roster_cache.update({str(emoji["id"]): user_mentions})

@mod_plugin.listener(hikari.ReactionEvent)
async def print_reaction(event: hikari.ReactionEvent) -> None:
    red_x_emoji_link = str(red_x_emoji["emoji"])
    if not isinstance(event, hikari.ReactionAddEvent) and not isinstance(event, hikari.ReactionDeleteEvent) :
        return
    
    # Ignore bot reactions
    if event.user_id == BOT_USER_ID :
        return
    
    if event.emoji_name != "🔔" :
        return
    
    if event.channel_id not in tracked_channel_ids:
        return;
    
    tracked_event = tracked_channel_ids.get(event.channel_id)
    
    if tracked_event and str(tracked_event.message.id) != str(event.message_id) :
        return;
    
    if isinstance(event, hikari.ReactionAddEvent):
        messages = await mod_plugin.bot.rest.fetch_messages(event.channel_id)
        for message in messages:
            if not message.content :
                continue;
            if "✅" in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
            if red_x_emoji_link in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
        
        interested_users.get(event.channel_id).append(event.user_id)
        await mod_plugin.bot.rest.create_message(event.channel_id, f" ✅ | <@{event.user_id}> | Interested in attending.")
    elif isinstance(event,hikari.ReactionDeleteEvent):
        messages = await mod_plugin.bot.rest.fetch_messages(event.channel_id)
        for message in messages:
            if not message.content :
                continue;
            if red_x_emoji_link in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
        await mod_plugin.bot.rest.create_message(event.channel_id, f" {red_x_emoji_link} | <@{event.user_id}> | No longer interested in attending the event.")
    else: 
        print(f"Unhandled Event Type: {event}")
    
    return

async def updateInterestedUsers(channel_id: str, message_id: str):
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=channel_id, message=message_id, emoji=emoji_dict.get("🔔")["emoji"])
    users = [user for user in iterator if user.id != BOT_USER_ID]
    interested_users.update({channel_id: users})

async def add_reaction(channel_id: str, message_id: str, emoji_name, emoji_id, emoji) -> None :
    await mod_plugin.bot.rest.add_reaction(channel=channel_id, message=message_id, emoji=emoji)
    saved_emoji = DefaultEmoji(name=emoji_name, id=emoji_id, emoji=emoji)
    emoji_dict.update({emoji_id: saved_emoji})

async def print_tracking_stages(tracking_stage: str, emoji_stage: str, interested_user_stage: str, roster_cache_stage: str, message: str) -> hikari.Embed:
    embed = hikari.Embed(title="Registering Event For Tracking...",color="#949fe6")
    embed.add_field(f"{tracking_stage} | Building Tracking Info...", "`                                        `")
    embed.add_field(f"{emoji_stage} | Adding Emojis to Message...", "`                                        `")
    embed.add_field(f"{interested_user_stage} | Verifying Already Interested Users...", "`                                        `")
    embed.add_field(f"{roster_cache_stage} | Building Roster Cache...", "`                                        `")
    discord_timestamp = generate_discord_timestamp(datetime.now())
    if roster_cache_stage != "✅":
        emoji_link = red_x_emoji["emoji"]
        embed.add_field(f"{emoji_link} | Working on Registering Event for Tracking.", message)
    else: 
        embed.add_field("✅ | Finished Registering Event for Tracking.", message)
    embed.add_field("`                                        `", f"Last update processed <t:{discord_timestamp}:R>")
    progress_state = 0 + (4 if tracking_stage == "✅" else 0)
    progress_state += 9 if emoji_stage == "✅" else 0
    progress_state += 3 if interested_user_stage == "✅" else 0
    progress_state += 15 if roster_cache_stage == "✅" else 0

    progress_bar = "" #31 long
    for _ in range(progress_state):
        progress_bar = f"{progress_bar}▓"

    for _ in range(31 - progress_state):
        progress_bar = f"{progress_bar}░"

    embed.set_footer(progress_bar)

    return embed

def generate_discord_timestamp(date_time: datetime):
    return calendar.timegm(date_time.utcnow().utctimetuple())

@mod_plugin.command
@lightbulb.option(
    "custom",
    "Enables custom reactions",
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
@lightbulb.command("track", "Begin tracking the associated post")
@lightbulb.implements(lightbulb.SlashCommand)
async def track_post(ctx: lightbulb.Context) -> None:  
    global red_x_emoji
    
    response_message = f"Tracking https://discord.com/channels/{ctx.guild_id}/{ctx.channel_id}/{ctx.options.message_id}"
    if ctx.options.event_id :
        response_message = f"{response_message} for https://discord.com/events/{ctx.guild_id}/{ctx.options.event_id}"
    
    if not red_x_emoji:
        emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
        for emoji in emojis :
            if str(emoji.id) == RED_X_EMOJI_ID :
                red_x_emoji = DefaultEmoji(name=emoji.name, id=emoji.id, emoji=emoji)
                break;
                
    embed = await print_tracking_stages(red_x_emoji["emoji"],red_x_emoji["emoji"],red_x_emoji["emoji"],red_x_emoji["emoji"], response_message)
    response = await ctx.respond(embed,flags=hikari.MessageFlag.EPHEMERAL)
    
    event = await build_tracking_info(ctx, response_message, response)
    
    await add_reactions_to_post(ctx, response_message, response)
    
    await updateInterestedUsers(channel_id=ctx.channel_id, message_id=ctx.options.message_id)
    
    embed = await print_tracking_stages("✅","✅","✅",red_x_emoji["emoji"], response_message)
    await response.edit(embed)
    
    await update_roster()
    
    embed = await print_tracking_stages("✅","✅","✅","✅", response_message)
    await response.edit(embed)

async def add_reactions_to_post(ctx, response_message, response):
    
    if not ctx.options.custom :
        await add_reaction(channel_id=ctx.channel_id, message_id=ctx.options.message_id, emoji_name="Interested", emoji_id="🔔", emoji="🔔")
        await add_reaction(channel_id=ctx.channel_id, message_id=ctx.options.message_id, emoji_name="New", emoji_id="🆕", emoji="🆕")
        await add_reaction(channel_id=ctx.channel_id, message_id=ctx.options.message_id, emoji_name="Filler", emoji_id="⭐", emoji="⭐")
        
        emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
        for emoji in emojis :
            if str(emoji.id) in EMOJI_IDS :
                saved_emoji = DefaultEmoji(name=emoji.name, id=emoji.id, emoji=emoji)
                emoji_dict.update({str(emoji.id): saved_emoji})
    
        for emoji_id in EMOJI_IDS :
            emoji = emoji_dict.get(str(emoji_id))
            await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=ctx.options.message_id, emoji=emoji["emoji"])
            
    embed = await print_tracking_stages("✅","✅",red_x_emoji["emoji"],red_x_emoji["emoji"], response_message)
    await response.edit(embed)

async def build_tracking_info(ctx, response_message, response):
    event_time = (datetime.now() + timedelta(days=ctx.options.timeout)).replace(tzinfo=pytz.UTC)
    
    channel = await mod_plugin.bot.rest.fetch_channel(channel=ctx.channel_id)
    message = await mod_plugin.bot.rest.fetch_message(channel=ctx.channel_id, message=ctx.options.message_id)
    event = None
    timeout = event_time
    if ctx.options.event_id :
        event = await mod_plugin.bot.rest.fetch_scheduled_event(ctx.guild_id,ctx.options.event_id)
        event_time = event.start_time.replace(tzinfo=pytz.UTC) - SERVER_TIME_OFFSET
    
    roster_cache = {}
    tracking_event = ForumEvent(channel, message, event, ctx.options.custom, roster_cache, event_time, timeout)
    
    tracked_channel_ids.update({ctx.channel_id: tracking_event})
    
    embed = await print_tracking_stages("✅",red_x_emoji["emoji"],red_x_emoji["emoji"],red_x_emoji["emoji"], response_message)
    await response.edit(embed)
    return event

async def fetch_emoji_info(forum_event, emoji):
    emoji_link = emoji["emoji"]
    users = await mod_plugin.bot.rest.fetch_reactions_for_emoji(forum_event.channel.id, message=forum_event.message.id, emoji=emoji_link)
    user_mentions = ""
    for user in users :
        if user not in interested_users[forum_event.channel.id] :
            continue;

        if user_mentions == "" :
            user_mentions = user.mention
        else :
            user_mentions = f"{user_mentions}, {user.mention}"

    return user_mentions if user_mentions != "" else "N/A"

async def createEmbedForReaction(ctx: lightbulb.Context, forum_event: ForumEvent) -> hikari.Embed:
    embed = hikari.Embed(title="PRE-ROSTER",color= "#949fe6")
    for emoji in emoji_dict.values() :
        if emoji["emoji"] == "🔔":
            continue
        user_mentions = forum_event.roster_cache.get(str(emoji["id"]))
        emoji_link = emoji["emoji"]
        reaction_name = emoji["name"].upper().replace("_", " ")
        embed.add_field(f"{emoji_link} | {reaction_name}", user_mentions)
    embed.set_footer("Message Mods/Admins if you need more help")
    return embed

@mod_plugin.command
@lightbulb.command("roster", "Displays everyone's playable roles based on their reactions to the post above.")
@lightbulb.implements(lightbulb.SlashCommand)
async def check_roster(ctx: lightbulb.Context) -> None:
    event = tracked_channel_ids.get(ctx.channel_id)
    
    if not event :
        await ctx.respond("Post is not currently being tracked.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    response = await ctx.respond(hikari.Embed(title="Fetching Pre-Roster..."),flags=hikari.MessageFlag.EPHEMERAL)
    embed = await createEmbedForReaction(ctx, event)
    await response.edit(embed=embed)

@mod_plugin.command
@lightbulb.command("main", "Allows a user to set a main role based on their reactions. Disabled for Custom Events.")
@lightbulb.implements(lightbulb.SlashCommand)
async def set_main(ctx:lightbulb.Context) -> None:
    event = tracked_channel_ids.get(ctx.channel_id)
    #TODO: Change to custom/default
    if event[1].custom == True :
        return;

def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(mod_plugin)