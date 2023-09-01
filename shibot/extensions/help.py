import hikari
import lightbulb

mod_plugin = lightbulb.Plugin("Help")

@mod_plugin.command
@lightbulb.command("help", "Gets help for bot commands",aliases=["Help","h"])
@lightbulb.implements(lightbulb.SlashCommand)
async def help(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="***Commands Available:***",color="#949fe6")
    embed.add_field("> `Track`", "Allows a user to mark an message for event tracking.")
    embed.add_field("> `Roster`", "Pulls the most recently retrieved roster.")
    embed.add_field("> `Main`", "Allows a user to mark their main role based on their reactions to a post.")
    embed.add_field("> `Authorize`", "Mods can authorize users to run restricted commands.")
    embed.add_field("> `Release Notes`", "Lastest patch notes.")
    await ctx.respond(embed, flags=hikari.MessageFlag.EPHEMERAL)
    
def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(mod_plugin)