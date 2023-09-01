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
    embed = Embed(title="Release Notes", color="#00ffff", url="https://github.com/twardle/DiscordBot_Hikari/blob/database")
    embed.add_field("`Database Integration`","*Ashebot's brainpower is off the charts!*")
    embed.add_field("`Listener Integrations`","*Ashebot won't get confused when things go missing anymore... probably.*")
    embed.add_field("`New Commands!`","*Ashebot got some new toys!*")
    embed.add_field("`More Cleanup`","*Ashebot's room has never been cleaner, let's hope it stays this way...*")
    embed.set_thumbnail("https://github.com/twardle/DiscordBot_Hikari/blob/database/Shiba_dev_logo.png?raw=true")
    embed.set_footer(f"Shibot {__version__}")
    
    if ctx.options.ephemeral :
        await ctx.respond(embed,flags=MessageFlag.EPHEMERAL)
    else :
        await ctx.respond(embed)
    log.info("*** | Finished Release Notes | ***")
    
def load(bot: lightbulb.BotApp) -> None:    
    bot.add_plugin(bot_plugin)