from shibot import helper, model, GUILD_ID, BOT_USER_ID, DEV_BOT_USER_ID, PROGRESS_BAR_LENGTH, MAX_LOADING_PERCENT, SERVER_TIME_OFFSET, RED_X_EMOJI_ID, EMOJI_IDS, __version__
import lightbulb
from hikari import *
import logging
from datetime import datetime, timedelta
import pytz
from typing import TypedDict, Dict, List, Iterable
from hikari.api.special_endpoints import MessageActionRowBuilder

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

bot_plugin = lightbulb.Plugin("Roster")

##########################################
##             INFO FETCHING            ##
##########################################

async def fetch_emoji_info(forum_event, emoji):
    global log
    emoji_name = emoji["name"]
    log.info(f"*** | Start Fetching Emoji Info For Post | Message: {forum_event.messageid} | Emoji: {emoji_name} | ***")
    
    emoji_link = emoji["emoji"]
    users = await bot_plugin.bot.rest.fetch_reactions_for_emoji(forum_event.channelid, message=forum_event.messageid, emoji=emoji_link)
    user_mentions = ""
    for user in users :
        # if str(user.id) not in interested_users[str(forum_event.channelid)] :
        #     continue
        
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

async def update_specific_roster(ctx: lightbulb.UserContext, forum_event) -> None: 
    log.info(f"*** | Start Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
    
    # red_x = red_x_emoji["emoji"]
    # timestamp = helper.generate_discord_timestamp(datetime.now())
    # roster_progress = 0
    # current_progress = 0
    
    embed = Embed(title="Updating Roster State...",color="#949fe6")
    # progress = helper.build_progress_bar(roster_progress,PROGRESS_BAR_LENGTH)
    # embed.add_field(f"{red_x} | Roster Loading...", progress)
    response = await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
    # iterator = await bot_plugin.bot.rest.fetch_reactions_for_emoji(channel=forum_event.channelid, message=forum_event.messageid, emoji=emoji_dict.get("🔔")["emoji"])
    # users = [str(user.id) for user in iterator if user.id != BOT_USER_ID]
    
    # interested_users.update({forum_event.channelid: users})
    
    # for emoji in emoji_dict.values() :
    #     current_progress += 1
    #     if emoji["emoji"] == "🔔":
    #         continue
    #     user_mentions = await fetch_emoji_info(forum_event, emoji)
    #     forum_event.roster_cache.update({str(emoji["id"]): user_mentions})
    #     roster_progress = (current_progress * PROGRESS_BAR_LENGTH) / len(emoji_dict.values())
    #     progress = helper.build_progress_bar(int(roster_progress),PROGRESS_BAR_LENGTH)
    #     embed = Embed(title="Updating Roster State...",color="#949fe6")
    #     embed.add_field(f"{red_x} | Roster Loading...", progress)
    #     await response.edit(embed)
    log.info(f"*** | Finish Updating Specific Roster For Main Command | Message: {forum_event.messageid} | ***")
    
    log.info(f"*** | Start Building Progress Bar For Main Command | Message: {forum_event.messageid} | ***")
    progress = helper.build_progress_bar(PROGRESS_BAR_LENGTH,PROGRESS_BAR_LENGTH)
    embed = Embed(title="Updating Roster State...",color="#949fe6")
    embed.add_field("✅ | Roster Loading...", progress)
    await response.edit(embed)
    log.info(f"*** | Finish Building Progress Bar For Main Command | Message: {forum_event.messageid} | ***")
    
    return response

async def createEmbedForReaction(ctx: lightbulb.Context, forum_event) -> Embed:
    log.info(f"*** | Start Generating Embed For Roster | Message: {forum_event.messageid} | ***")
    embed = Embed(title="PRE-ROSTER",color= "#949fe6")
    
    if not forum_event.roster_cache :
        embed.add_field("Roster not generated yet for post", "Please contact dev if this persists.")
        log.info(f"*** | Finish Generating Embed For Roster | Message: {forum_event.messageid} | ***")
        return embed
        
    # for emoji in emoji_dict.values() :
    #     if emoji["emoji"] == "🔔":
    #         continue
    #     user_mentions = forum_event.roster_cache.get(str(emoji["id"]))
    #     emoji_link = emoji["emoji"]
    #     reaction_name = emoji["name"].upper().replace("_", " ")
    #     embed.add_field(f"{emoji_link} | {reaction_name}", user_mentions)
    embed.set_footer("Message Mods/Admins if you need more help")
    log.info(f"*** | Finish Generating Embed For Roster | Message: {forum_event.messageid} | ***")
    return embed

@bot_plugin.command
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
    
    event = tracked_channels.get(f"{ctx.channel_id}")
    
    if not event :
        await ctx.respond("Post is not currently being tracked.", flags=MessageFlag.EPHEMERAL)
        return
    
    # if ctx.options.force_reload :
    #     # response = await update_specific_roster(ctx, event)
        
    #     if response is None :
            # return
    
    response = await ctx.respond(Embed(title="Fetching Pre-Roster..."),flags=MessageFlag.EPHEMERAL)
    # embed = await createEmbedForReaction(ctx, event)
    # await response.edit(embed=embed)
    
def load(bot: lightbulb.BotApp) -> None:    
    bot.add_plugin(bot_plugin)