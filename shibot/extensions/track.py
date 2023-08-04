import lightbulb
from hikari import *
import logging
from datetime import datetime, timedelta
import pytz
from typing import TypedDict, Dict, List, Iterable
from shibot import helper, model, GUILD_ID, BOT_USER_ID, DEV_BOT_USER_ID, PROGRESS_BAR_LENGTH, MAX_LOADING_PERCENT, SERVER_TIME_OFFSET, RED_X_EMOJI_ID, EMOJI_IDS, __version__

bot_plugin = lightbulb.Plugin("Track")

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

red_x_emoji = None
emoji_cache = {}

##########################################
##              VALIDATION              ##
##########################################

async def validate_authorized_user(ctx:lightbulb.Context) -> bool:
    global log
    log.info(f"*** | Start Validating Authorized User | Message: {ctx.options.message_id} | User: {ctx.author} | ***")
    now = datetime.now(pytz.timezone('America/New_York')).strftime("%m/%d/%Y %I:%M:%S %p")

    if authorized := model.Authorized.get_or_none(
        channel=ctx.channel_id, user=ctx.author.id
    ):
        log.info(f"*** | Finish Validating Authorized User | Message: {ctx.options.message_id} | User: {ctx.author} | Executed /{ctx.command.name} | ***")
        return True
    else:
        embed = Embed(title="UNAUTHORIZED USER",color="#880808")
        embed.set_footer("Unable to execute command")
        await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
        log.error(f"{now} | Unauthorized Command Attempt |  {ctx.author} | {ctx.get_channel().name} | Attempted to execute /{ctx.command.name}")
        return False

##########################################
##           TRACKING METHODS           ##
##########################################

async def build_tracking_info(ctx: lightbulb.Context, channel_id, message_id, event_id, response_message, response, tracking, reaction):
    global log
    log.info(f"*** | Start Building Tracking Info For Post | Message: {message_id} | ***")
    timestamp = helper.generate_discord_timestamp(datetime.now())
    event_time = (datetime.now() + timedelta(days=ctx.options.timeout)).replace(tzinfo=pytz.UTC)
    
    event = None
    timeout = event_time
    if ctx.options.event_id :
        event = await bot_plugin.bot.rest.fetch_scheduled_event(ctx.guild_id,event_id)
        event_time = event.start_time.replace(tzinfo=pytz.UTC) - SERVER_TIME_OFFSET
    
    tracking = model.Track.get_or_none(channel=int(channel_id), message=int(message_id)) 
    
    if not tracking:
        tracking = model.Track.create(channel=int(channel_id), message=int(message_id),creator=int(ctx.author.id), event=event_id)
    
    roster = model.Roster.get_or_none(track=tracking.id)
    
    if not roster:
        model.Roster.create(track=tracking.id, updated_at=datetime.now())
    
    log.info(f"*** | Finish Building Tracking Info For Post | Message: {message_id} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Post | Update Tracking Stage | Message: {message_id} | ***")
    tracking = ["✅",helper.build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Post | Update Tracking Stage | Message: {message_id} | ***")
    
    return tracking

async def add_reactions_to_post(ctx, message:PartialMessage, response_message, response, tracking,reaction):
    global log
    log.info(f"*** | Start Adding Reactions To Post | Message: {message.id} | ***")
    timestamp = helper.generate_discord_timestamp(datetime.now())

    iterator = await bot_plugin.bot.rest.fetch_reactions_for_emoji(channel=ctx.channel_id, message=message.id, emoji="🔔")
    for message_reactions in message.reactions:
        if message_reactions.emoji == "🔔" and message_reactions.is_me:
            reaction = ["✅",helper.build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
            embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
            await response.edit(embed)
            log.info(f"*** | Finish Adding Reactions To Post | Already Added | Message: {message.id} | ***")
            return reaction

    reaction_progress = 0
    current_progress = 0
    
    await message.add_reaction(emoji="🔔")
    await message.add_reaction(emoji="🆕")
    await message.add_reaction(emoji="⭐")

    if ctx.options.custom:
        reaction = ["✅",helper.build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
        await response.edit(embed)

        log.info(f"*** | Finish Adding Reactions To Post | Custom Post | Message: {message.id} | ***")
        return reaction

    current_progress = 3

    reaction_progress = int((current_progress * PROGRESS_BAR_LENGTH) / (len(EMOJI_IDS)+3))
    reaction = [red_x_emoji,helper.build_progress_bar(reaction_progress, PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
    await response.edit(embed)

    for emoji_id in EMOJI_IDS :
        current_progress+= 1
        await message.add_reaction(emoji=emoji_cache.get(emoji_id))
        reaction_progress = (current_progress * PROGRESS_BAR_LENGTH) / (len(EMOJI_IDS)+3)
        reaction = [red_x_emoji,helper.build_progress_bar(int(reaction_progress),PROGRESS_BAR_LENGTH)]
        embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
        await response.edit(embed)
    log.info(f"*** | Finish Adding Reactions To Post | Message: {message.id} | ***")

    log.info(f"*** | Start Building Progress Bar For Post | Update Reaction Stage | Message: {message.id} | ***")
    reaction = ["✅",helper.build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(timestamp, tracking,reaction,response_message)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Post | Update Reaction Stage | Message: {message.id} | ***")

    return reaction

async def print_tracking_stages(timestamp, tracking_stage, reaction_stage, message: str) -> Embed:
    total_progress_amount = calc_total_progress(tracking_stage, reaction_stage)
    
    embed = Embed(title="Registering Event For Tracking...",color="#949fe6")
    
    embed.add_field(f"{tracking_stage[0]} | Building Tracking Info...", tracking_stage[1])
    progress_state = int((3 * int(tracking_stage[1].count('▓'))) / PROGRESS_BAR_LENGTH)

    embed.add_field(f"{reaction_stage[0]} | Adding Emojis to Message...", reaction_stage[1])
    progress_state += int((22 * int(reaction_stage[1].count('▓'))) / PROGRESS_BAR_LENGTH)
    
    if reaction_stage[0] != "✅":
        embed.add_field(f"{red_x_emoji} | Working on Registering Event for Tracking.", message)
    else: 
        embed.add_field("✅ | Finished Registering Event for Tracking.", message)
    
    progress_bar = helper.build_progress_bar(progress_state=progress_state, max_state=PROGRESS_BAR_LENGTH)
    
    embed.add_field(progress_bar, f"Last update processed <t:{timestamp}:R>")

    return embed

def calc_total_progress(tracking_stage, reaction_stage):
    tracking_progress_amount = int(tracking_stage[1].count('▓'))
    reaction_progress_amount = int(reaction_stage[1].count('▓'))
    return int(
        (
            (
                tracking_progress_amount
                + reaction_progress_amount
            )
            / (PROGRESS_BAR_LENGTH * 2)
        )
        * PROGRESS_BAR_LENGTH
    )

##########################################
##               COMMANDS               ##
##########################################

@bot_plugin.command
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
    
    message_id : str = ctx.options.message_id
    if "https://discord.com/" in message_id :
        message_id = message_id.split("/")[-1]
    
    message = await build_db_entities(ctx, message_id)
    
    authorized = await validate_authorized_user(ctx)
    
    if authorized == False:
        return
    
        
    event_id : str = ctx.options.event_id
    if event_id and "https://discord.com/" in event_id :
        event_id = event_id.split("/")[-1]
    
    response_message = f"Tracking https://discord.com/channels/{ctx.guild_id}/{ctx.channel_id}/{message.id}"
    if ctx.options.event_id :
        response_message = f"{response_message} for https://discord.com/events/{ctx.guild_id}/{event_id}"
    
    discord_timestamp = helper.generate_discord_timestamp(datetime.now())
    tracking = [red_x_emoji,helper.build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    reaction = [red_x_emoji,helper.build_progress_bar(0,PROGRESS_BAR_LENGTH)]
    embed = await print_tracking_stages(discord_timestamp,tracking,reaction,response_message)
    response = await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
    
    tracking = await build_tracking_info(ctx, ctx.get_channel().id, message.id, event_id, response_message,response,tracking,reaction)
    reaction = await add_reactions_to_post(ctx, message, response_message, response, tracking,reaction)
    
    now = datetime.now(pytz.timezone('America/New_York')).strftime("%m/%d/%Y %I:%M:%S %p")
    log.info(f"*** | Authorized Command Complete | {ctx.author} | {ctx.get_channel().name} | Executed /{ctx.command.name} | ***")

async def build_db_entities(ctx: lightbulb.Context, message_id: str) -> PartialMessage:
    guild_owner:model.User = model.User.get_or_none(id=int(ctx.get_guild().owner_id))
    
    if not guild_owner:
        guild_owner:PartialUser = await bot_plugin.bot.rest.fetch_user(user=ctx.get_guild().owner_id)
        guild_owner:model.User = model.User.get_or_create(
                id=int(guild_owner.id), 
                is_bot=guild_owner.is_bot, 
                username=guild_owner.username, 
                mention=guild_owner.mention
            )
    
    guild = model.Guild.get_or_none(id=ctx.guild_id)
    
    if not guild:
        guild = model.Guild.create(
                id=ctx.guild_id, 
                name=str(ctx.get_guild().name), 
                description=str(ctx.get_guild().description),
                owner=int(ctx.get_guild().owner_id)
            )
    
    parent_channel = model.Channel.get_or_none(
            id=ctx.get_channel().parent_id, 
            guild=ctx.guild_id
        )
    
    if ctx.get_channel().parent_id and not parent_channel:
        guild_parent_channel = await bot_plugin.bot.rest.fetch_channel(channel=ctx.get_channel().parent_id)
        parent_channel = model.Channel.create(
                id=guild_parent_channel.id, 
                name=str(guild_parent_channel.name),
                type=int(guild_parent_channel.type),
                mention=str(guild_parent_channel.mention),
                guild=ctx.guild_id
            )
    
    channel = model.Channel.get_or_none(
            id=ctx.channel_id, 
            guild=ctx.guild_id
        )
    
    if not channel: 
        channel = model.Channel.create(
                id=ctx.channel_id, 
                name=str(ctx.get_channel().name), 
                parent=int(ctx.get_channel().parent_id), 
                type=int(ctx.get_channel().type), 
                mention=str(ctx.get_channel().mention), 
                guild=ctx.guild_id
            )
        
        if isinstance(ctx.get_channel(), GuildThreadChannel):
            authorized = model.Authorized.create(
                user=ctx.get_channel().owner_id, 
                channel=ctx.channel_id
            )
    
    guild_message:PartialMessage = await bot_plugin.bot.rest.fetch_message(message=message_id, channel=ctx.channel_id)
    
    message = model.Message.get_or_none(
            id=message_id, 
            channel=ctx.channel_id, 
            guild=ctx.guild_id
        )
    
    if not message:
        message = model.Message.create(
                id=message_id, 
                author=int(guild_message.author.id), 
                channel=int(guild_message.channel_id), 
                type=int(guild_message.type), 
                content=str(guild_message.content), 
                sent_at=guild_message.created_at, 
                edited_at=guild_message.edited_timestamp, 
                guild=ctx.guild_id
            )
    
    red_x_emoji = await bot_plugin.bot.rest.fetch_emoji(guild=GUILD_ID,emoji=RED_X_EMOJI_ID)

    emojis = await bot_plugin.bot.rest.fetch_guild_emojis(guild=GUILD_ID)
    for emoji in emojis :
        emoji_id = str(emoji.id)
        if emoji_id in EMOJI_IDS :
            emoji_db = model.Emoji.get_or_none(id=int(emoji_id))
            
            if not emoji_db:
                model.Emoji.create(
                    id=int(emoji_id), 
                    name=str(emoji.name), 
                    mention=str(emoji.mention),
                    url=str(emoji.url),
                    url_name=str(emoji.url_name), 
                    guild=int(emoji.guild_id)
                )
            
            # message.add_reaction(emoji=emoji)
            emoji_cache.update({emoji_id: emoji})
    
    return guild_message

def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(bot_plugin)