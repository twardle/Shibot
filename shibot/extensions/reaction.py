# TODO: Add Custom vs Default Mode
# TODO: Add /Main Command for individual users
# TODO: Add Redundancies to prevent people tracking others events
# TODO: Add /Special Roles command
# TODO: Ensure 🔔 icon is the first emote
# TODO: Order Users by Signup Order
# FEATURE REQUEST: Sample Roster
# FEATURE REQUEST: DM Sign ups before event
# FEATURE REQUEST: 

import lightbulb
import hikari
import pytz
from typing import TypedDict
from pytz import timezone
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from shibot import GUILD_ID

class DefaultEmoji(TypedDict):
    name: str
    id: int
    emoji: hikari.Emoji

class ForumEvent:
    def __init__(self, channel: hikari.GuildChannel, message: hikari.Message, event: hikari.GuildEvent, custom: bool, event_timeout: datetime, tracking_timeout: datetime):
        self.channel = channel
        self.message = message
        self.event = event
        self.custom = custom
        self.event_timeout = event_timeout
        self.tracking_timeout = tracking_timeout
    
SERVER_TIME_OFFSET = timedelta(hours=4)
EMOJI_IDS = [
    "1108505145697898647", # Quick Heal
    "1108505147149131776", # Alac Heal
    "1108505150827544696", # Quick DPS
    "1108505144737402901", # Alac DPS
    "1108505149154009220", # Condi DPS
    "1108505148201902182", # Power DPS
    ]

tracked_channel_ids = {}
emoji_dict = {}
interested_users = {}
mod_plugin = lightbulb.Plugin("Reaction")

sched = AsyncIOScheduler()
sched.start()

@sched.scheduled_job(CronTrigger(minute="*/5"))
async def check_old_events() -> None:
    print(tracked_channel_ids)
    to_remove = [
        event[0]
        for event in tracked_channel_ids.items()
        if event[1].event_timeout - timedelta(minutes=5) < datetime.now().replace(tzinfo=pytz.UTC)
    ]
    print(to_remove)
    
    for key in to_remove:
        tracked_channel_ids.pop(key)
        await mod_plugin.bot.rest.create_message(key, f"<#{key}> | Event signup period has ended.")

@mod_plugin.listener(hikari.ReactionEvent)
async def print_reaction(event: hikari.ReactionEvent) -> None:
    # print(event)
    
    if not isinstance(event, hikari.ReactionAddEvent) and not isinstance(event, hikari.ReactionDeleteEvent) :
        return
    
    # Ignore bot reactions
    if event.user_id == 1106386632749350912 :
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
            if "✅" in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
            if "❎" in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
        interested_users.get(event.channel_id).append(event.user_id)
        await mod_plugin.bot.rest.create_message(event.channel_id, f" ✅ | <@{event.user_id}> | Interested in attending.")
    elif isinstance(event,hikari.ReactionDeleteEvent):
        messages = await mod_plugin.bot.rest.fetch_messages(event.channel_id)
        for message in messages:
            if "❎" in message.content and f"{event.user_id}" in message.content :
                await mod_plugin.bot.rest.delete_message(message=message.id, channel=event.channel_id)
        await mod_plugin.bot.rest.create_message(event.channel_id, f" ❎ | <@{event.user_id}> | No longer interested in attending the event.")
    else: 
        print(f"Unhandled Event Type: {event}")
    
    return

async def updateInterestedUsers(channel_id: str, message_id: str):
    iterator = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=channel_id, message=message_id, emoji=emoji_dict.get("🔔")["emoji"])
    users = []
    for user in iterator :
        # Ignore bot reactions
        if user.id == 1106386632749350912 :
            continue
        users.append(user)
    
    interested_users.update({channel_id: users})
    # print(interested_users)


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
    response = await ctx.respond("Building Tracking Info...",flags=hikari.MessageFlag.EPHEMERAL)
    
    event_time = (datetime.now() + timedelta(days=ctx.options.timeout)).replace(tzinfo=pytz.UTC)
    
    # if ctx.options.message_id : 
    #     ctx.options.message_id = ctx.options.message_id
    # else :
    #     messages = await mod_plugin.bot.rest.fetch_messages(channel=ctx.channel_id)
    #     messages.sort(key=lambda x: x.created_at)
    #     message_id = messages[0].id
    
    channel = await mod_plugin.bot.rest.fetch_channel(channel=ctx.channel_id)
    message = await mod_plugin.bot.rest.fetch_message(channel=ctx.channel_id, message=ctx.options.message_id)
    event = None
    timeout = event_time
    if ctx.options.event_id :
        event = await mod_plugin.bot.rest.fetch_scheduled_event(ctx.guild_id,ctx.options.event_id)
        event_time = event.start_time.replace(tzinfo=pytz.UTC) - SERVER_TIME_OFFSET
    
    tracking_event = ForumEvent(channel, message, event, ctx.options.custom, event_time, timeout)    
    tracked_channel_ids.update({ctx.channel_id: tracking_event})
    
    if not ctx.options.custom :
        await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=ctx.options.message_id, emoji="🔔")
        saved_emoji = DefaultEmoji(name="Interested", id="🔔", emoji="🔔")
        emoji_dict.update({"🔔": saved_emoji})
        await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=ctx.options.message_id, emoji="🆕")
        saved_emoji = DefaultEmoji(name="New", id="🆕", emoji="🆕")
        emoji_dict.update({"🆕": saved_emoji})
        await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=ctx.options.message_id, emoji="⭐")
        saved_emoji = DefaultEmoji(name="Filler", id="⭐", emoji="⭐")
        emoji_dict.update({"⭐": saved_emoji})
        
        emojis = await mod_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
        # print(emojis)
        for emoji in emojis :
            if str(emoji.id) in EMOJI_IDS :
                saved_emoji = DefaultEmoji(name=emoji.name, id=emoji.id, emoji=emoji)
                emoji_dict.update({str(emoji.id): saved_emoji})
    
        for emoji_id in EMOJI_IDS :
            emoji = emoji_dict.get(str(emoji_id))
            await mod_plugin.bot.rest.add_reaction(channel=ctx.channel_id, message=ctx.options.message_id, emoji=emoji["emoji"])
    
    
    await updateInterestedUsers(channel_id=ctx.channel_id, message_id=ctx.options.message_id)
    
    response_message = f"Successfully Tracking https://discord.com/channels/{ctx.guild_id}/{ctx.channel_id}/{ctx.options.message_id}"
    if event :
        print(emojis = await mod_plugin.bot.rest.fetch_guild_emojis(ctx.guild_id))
        response_message = f"{response_message} for https://discord.com/events/{ctx.guild_id}/{ctx.options.event_id}"
    
    await response.edit(response_message)

def sorting_algorithm(x):
    if isinstance(x.emoji, hikari.CustomEmoji):
        return x.emoji.name
    else :
        return x.emoji

async def createEmbedForReaction(ctx: lightbulb.Context, forum_event: ForumEvent) -> hikari.Embed:
    embed = hikari.Embed(title="PRE-ROSTER",color= "#949fe6")
    # valid_users = []
    
    # for emoji in emoji_dict.values() :
    #     if emoji["name"] != "🔔":
    #         continue
        
    #     valid_users = await mod_plugin.bot.rest.fetch_reactions_for_emoji(channel=ctx.channel_id, message=messageId, emoji=reaction.emoji)
            
    for emoji in emoji_dict.values() :
        if emoji["emoji"] == "🔔":
            continue
        
        emoji_link = emoji["emoji"]
        print(emoji_link)
        users = await mod_plugin.bot.rest.fetch_reactions_for_emoji(forum_event.channel.id, message=forum_event.message.id, emoji=emoji_link)
        user_mentions = ""
        for user in users :
            if user not in interested_users[forum_event.channel.id] :
                continue;
            
            if user_mentions == "" :
                user_mentions = user.mention
            else :
                user_mentions = f"{user_mentions}, {user.mention}"
        
        user_mentions = user_mentions if user_mentions != "" else "N/A"
        reaction_name = emoji["name"].upper().replace("_", " ")
        embed.add_field(f"{emoji_link} | {reaction_name}", user_mentions)
    embed.set_footer("Message Mods/Admins if you need more help")
    return embed

@mod_plugin.command
@lightbulb.command("roster", "Displays everyone's playable roles based on their reactions to the post above.")
@lightbulb.implements(lightbulb.SlashCommand)
async def check_roster(ctx: lightbulb.Context) -> None:
    print(tracked_channel_ids)
    event = tracked_channel_ids.get(ctx.channel_id)
    
    if not event :
        await ctx.respond("Post is not currently being tracked.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    response = await ctx.respond(hikari.Embed(title="Fetching Pre-Roster..."),flags=hikari.MessageFlag.EPHEMERAL)
    # message = await mod_plugin.bot.rest.fetch_message(message=event[0], channel=ctx.channel_id)
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