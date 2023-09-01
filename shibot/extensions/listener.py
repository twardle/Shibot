# TODO: Add /Special Roles command
# TODO: Add /Authorize command
# TODO: Order Users by Signup Order
# FEATURE REQUEST: Sample Roster
# FEATURE REQUEST: DM Sign ups before event
# FEATURE REQUEST: Low Priority (Not Filler)

import logging
import lightbulb
from hikari import *
from datetime import datetime
from shibot import model, GUILD_ID, BOT_USER_ID, DEV_BOT_USER_ID,RED_X_EMOJI_ID, __version__

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
##               VARIABLES              ##
##########################################

bot_plugin = lightbulb.Plugin("Listener")

##########################################
##              EVENT EVENTS            ##
##########################################

@bot_plugin.listener(ScheduledEventEvent)
async def event_listener(event: ScheduledEventEvent) -> None:
    log.info("*** | Start Handle Scheduled Event Event | ***")
    if not isinstance(event, ScheduledEventUpdateEvent) and not isinstance(event, ScheduledEventDeleteEvent):
        log.info("*** | Finish Handle Scheduled Event Event | Not Update/Delete | ***")
        return

    log.info(event)

    scheduled_event:model.Event = model.Event.get_or_none(guild = event.event.guild_id, id = event.event.id)
    
    if not scheduled_event:
        return
    
    if isinstance(event, ScheduledEventDeleteEvent) or event.event.status in (ScheduledEventStatus.CANCELED,ScheduledEventStatus.CANCELLED,ScheduledEventStatus.COMPLETED) :
        #TODO: Message author in DMs to cancel event
        
        scheduled_event.delete_instance()
    else :
        scheduled_event.status=event.event.status.value
        scheduled_event.description = event.event.description
        scheduled_event.save()

##########################################
##            DIRECTORY EVENTS          ##
##########################################

@bot_plugin.listener(ChannelEvent)
async def channel_listener(event: ChannelEvent) -> None:
    log.info("*** | Start Handle Channel Event | ***")
    if not isinstance(event, GuildChannelDeleteEvent):
        log.info("*** | Finish Handle Channel Event | Not Delete | ***")
        return

    log.info(event)

    if channel := model.Channel.get_or_none(
        guild=event.guild_id,
        id=event.channel_id
    ):
        channel.delete_instance()

##########################################
##             MESSAGE EVENTS           ##
##########################################

@bot_plugin.listener(MessageEvent)
async def message_listener(event: MessageEvent) -> None:
    log.info("*** | Start Handle Message Event | ***")
    if not isinstance(event, MessageDeleteEvent) and not isinstance(event, MessageUpdateEvent):
        log.info("*** | Finish Handle Message Event | Not Update/Delete | ***")
        return

    # TODO: Ignore bot reactions
    if event.message.author.id in [BOT_USER_ID, DEV_BOT_USER_ID]:
        log.info("*** | Finish Handle Message Event | Bot User | ***")
        return

    log.info(event)
    
    message: model.Message =  model.Message.get_or_none(guild = event.message.guild_id, channel = event.message.channel_id, id = event.message.id)
    
    if not message:
        return
    
    if isinstance(event, MessageDeleteEvent) :
        message.delete_instance()
    else :
        message.content = event.content
        message.edited_at = datetime.now()
        
        message.save()

##########################################
##            REACTION EVENTS           ##
##########################################

@bot_plugin.listener(ReactionEvent)
async def reaction_listener(event: ReactionEvent) -> None:
    log.info("*** | Start Handle Reaction Event | ***")
    if not isinstance(event, ReactionAddEvent) and not isinstance(event, ReactionDeleteEvent) :
        log.info("*** | Finish Handle Reaction Event | Not Add/Delete | ***")
        return

    # Ignore bot reactions
    if event.user_id in [BOT_USER_ID, DEV_BOT_USER_ID]:
        log.info("*** | Finish Handle Reaction Event | Bot User | ***")
        return

    log.info(event)

    user = model.User.get_or_none(id=event.user_id)

    if not user:
        fetched_user:PartialUser = await bot_plugin.app.rest.fetch_user(user=event.user_id)

        model.User.create(
            id=event.user_id,
            username=fetched_user,
            mention=fetched_user.mention,
            is_bot=fetched_user.is_bot
        )

    tracked_event:model.Track = model.Track.get_or_none(channel=int(event.channel_id),message=int(event.message_id))

    if not tracked_event :
        log.info("*** | Finish Handle Reaction Event | Not a Tracked Message | ***")
        return;

    roster:model.Roster = model.Roster.get(track=tracked_event.id)

    if isinstance(event, ReactionAddEvent):
        model.RosterEntry.create(
                emoji=event.emoji_id, 
                emoji_name=event.emoji_name,
                roster=roster.id,
                user=user.id,
                created_at=datetime.now()
            )

        if event.emoji_name == "🔔":
            await handle_interested_reaction_add_event(event)
        else:
            await handle_reaction_add_event(event)

        roster.updated_at=datetime.now()
        roster.save()
    elif isinstance(event,ReactionDeleteEvent):
        roster_entry = model.RosterEntry.get(emoji=event.emoji_id, emoji_name=event.emoji_name, roster=roster.id)
        roster_entry.delete_instance()

        if event.emoji_name == "🔔":
            await handle_interested_reaction_delete_event(event)
        else: 
            await handle_reaction_delete_event(event)

        roster.updated_at=datetime.now()
        roster.save()
    else: 
        event_string = str(event).encode("utf-8")
        log.error(f"Unhandled Event Type: {event_string}")

    log.info("*** | Finish Handle Reaction Event | ***")

    return

async def handle_interested_reaction_delete_event(reaction_event:ReactionAddEvent):
    log.info("*** | Start Handle Reaction Delete Event | ***")
    
    red_x_emoji = model.Emoji.get(guild=GUILD_ID,id=RED_X_EMOJI_ID)
    
    messages = await bot_plugin.bot.rest.fetch_messages(reaction_event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if red_x_emoji.mention in message.content and f"{reaction_event.user_id}" in message.content :
            await bot_plugin.bot.rest.delete_message(message=message.id, channel=reaction_event.channel_id)
    await bot_plugin.bot.rest.create_message(reaction_event.channel_id, f" {red_x_emoji.mention} | <@{reaction_event.user_id}> | No longer interested in attending the event.")
    
    log.info("*** | Finish Handle Reaction Delete Event | ***")


async def handle_reaction_delete_event(reaction_event:ReactionAddEvent):
    # TODO: DO NOTHING
    return

async def handle_interested_reaction_add_event(reaction_event:ReactionAddEvent):
    log.info("*** | Start Handle Reaction Add Event | ***")
    
    red_x_emoji = model.Emoji.get(guild=GUILD_ID,id=RED_X_EMOJI_ID)
    
    messages = await bot_plugin.bot.rest.fetch_messages(reaction_event.channel_id)
    for message in messages:
        if not message.content :
            continue;
        if "✅" in message.content and f"{reaction_event.user_id}" in message.content :
            await bot_plugin.bot.rest.delete_message(message=message.id, channel=reaction_event.channel_id)
        if red_x_emoji.mention in message.content and f"{reaction_event.user_id}" in message.content :
            await bot_plugin.bot.rest.delete_message(message=message.id, channel=reaction_event.channel_id)
    
    await bot_plugin.bot.rest.create_message(reaction_event.channel_id, f" ✅ | <@{reaction_event.user_id}> | Interested in attending.")
    
    log.info("*** | Finish Handle Reaction Add Event | ***")


async def handle_reaction_add_event(reaction_event:ReactionAddEvent):
    # TODO: DO NOTHING
    return
    
def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(bot_plugin)