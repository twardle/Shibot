from shibot import __version__
import lightbulb
from hikari import *
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

bot_plugin = lightbulb.Plugin("Release")

@bot_plugin.command
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
    embed = Embed(title="Release Notes", color="#00ffff", url="https://github.com/twardle/DiscordBot_Hikari/blob/master")
    embed.add_field("Safe Reboot","*Shibot will now remember things, even after unexpected naps!*")
    embed.add_field("Performance Enhancements","*Shibot's zoomies are off the charts thanks to being a bit more lazy!*")
    embed.add_field("Caching Cleanup","*Shibot now only remembers the important things...*")
    embed.add_field("Logging Handling","*Shibot sometimes makes mistakes, and that's ok.*")
    embed.set_thumbnail("https://github.com/twardle/DiscordBot_Hikari/blob/master/Shiba_logo.png?raw=true")
    embed.set_footer(f"Shibot {__version__}")
    
    if ctx.options.ephemeral :
        await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
    else :
        await ctx.respond(embed)
    log.info("*** | Finished Release Notes | ***")
    
def load(bot: lightbulb.BotApp) -> None:    
    bot.add_plugin(bot_plugin)