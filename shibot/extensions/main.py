from shibot import helper, model, GUILD_ID, BOT_USER_ID, DEV_BOT_USER_ID, PROGRESS_BAR_LENGTH, MAX_LOADING_PERCENT, SERVER_TIME_OFFSET, RED_X_EMOJI_ID, EMOJI_IDS, __version__
import lightbulb
from hikari import *
import logging
from datetime import datetime
from typing import List, Iterable
from hikari.api.special_endpoints import MessageActionRowBuilder

bot_plugin = lightbulb.Plugin("Main")

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

emoji_cache = {}

async def handle_response_main(ctx:lightbulb.Context, bot: lightbulb.BotApp,author: User,message: Message, track: model.Track, footer, ) -> None:
    with bot.stream(InteractionCreateEvent, 120).filter(

                        lambda e: (isinstance(e.interaction, ComponentInteraction) and e.interaction.user == author and e.interaction.message == message)
                    ) as stream:
        async for event in stream:
            log.info(f"*** | Start Handling Response For Main Command | Message: {track.message} | User: {author.username} | ***")
            cid = event.interaction.custom_id

            main = model.Emoji.get(name=cid)

            emoji = emoji_cache.get(main.id)
            if not emoji:
                emoji = await bot_plugin.bot.rest.fetch_emoji(guild=ctx.get_guild().id,emoji=main.id)
                emoji_cache.update({main.id:emoji})

            main_name = main.name.upper().replace("_", " ")

            roster:model.Roster = model.Roster.get(track=track.id)

            if entry := model.RosterEntry.get_or_none(
                roster=roster.id,
                user=author.id,
                emoji=main.id,
                emoji_name=main.name,
            ):

                if old_main := model.RosterEntry.get_or_none(
                    roster=roster.id, user=author.id, main=True
                ):
                    old_main.main=False
                    old_main.updated_at=datetime.now()
                    old_main.save()

                entry.main = True
                entry.updated_at=datetime.now()
                entry.main=True
                entry.save()
                embed = Embed(title=main_name,description=f"Main set to {emoji} {main_name}",)
            else:
                embed = Embed(title="Invalid Main Attempted",description=f"Please react first | {emoji} {main_name}.",color="#880808")

            if footer : embed.set_footer(footer)

            try:
                await event.interaction.create_initial_response(ResponseType.MESSAGE_UPDATE,embed=embed)
            except NotFoundError:
                await event.interaction.edit_initial_response(embed=embed,)

            log.info(f"*** | Finish Handling Response For Main Command | Message: {track.message} | User: {author.username} | ***")

    try:
        await message.edit(components=[])
    except NotFoundError:
        return

async def generate_buttons_for_main(track: model.Track, user_id: str, bot: lightbulb.BotApp) -> Iterable[MessageActionRowBuilder]:
    log.info(f"*** | Start Generating Buttons For Main Embed | Message: {track.message} | ***")

    rows: List[MessageActionRowBuilder] = []

    row = bot.rest.build_message_action_row()

    for i in range(len(EMOJI_IDS)):
        emoji = emoji_cache.get(EMOJI_IDS[i])
        emoji_values = model.Emoji.get_by_id(EMOJI_IDS[i])
        
        if i % 3 == 0 and i != 0:
            rows.append(row)
            row = bot.rest.build_message_action_row()

        row.add_interactive_button(
            ButtonStyle.SECONDARY,
            emoji_values.name,
            emoji=emoji,
            label=emoji_values.name.upper().replace("_", " "),
        )

    rows.append(row)
    log.info(f"*** | Finish Generating Buttons For Embed | Message: {track.message} | ***")

    return rows

@bot_plugin.command
@lightbulb.command("main", "Allows a user to set a main role based on their reactions. Disabled for Custom Events.")
@lightbulb.implements(lightbulb.SlashCommand)
async def set_main(ctx:lightbulb.Context) -> None:
    track = model.Track.get_or_none(channel=ctx.channel_id)
    
    if not track or track.custom == True :
        log.error(f"Failed to load {ctx.channel_id}, not in tracked events.")
        embed = Embed(title="INVALID CHANNEL",color="#880808")
        embed.set_footer("This channel has not been added to tracked events.")
        await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
        return;
    
    if not emoji_cache:
        await build_emoji_cache()
    
    rows = await generate_buttons_for_main(track, str(ctx.author.id), ctx.bot)
    response = await ctx.respond(Embed(title="Pick a Main"),components=rows,flags=MessageFlag.EPHEMERAL)
    message = await response.message()
    footer = None
    try:
        await handle_response_main(ctx, ctx.bot, ctx.author, message, track, footer)
    except lightbulb.CommandInvocationError:
        return


async def build_emoji_cache():
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


def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(bot_plugin)