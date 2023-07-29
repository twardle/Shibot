import hikari
import lightbulb

mod_plugin = lightbulb.Plugin("Test")

@mod_plugin.command
@lightbulb.option("repeat", "text to repeat", modifier=lightbulb.OptionModifier.CONSUME_REST)
@lightbulb.command("repeat","repeats text")
@lightbulb.implements(lightbulb.SlashCommand)
async def echo(ctx: lightbulb.Context) -> None:
    await ctx.respond(ctx.options.repeat)

@mod_plugin.command
@lightbulb.command("test", "Gets help for bot commands")
@lightbulb.implements(lightbulb.SlashCommand)
async def test(ctx: lightbulb.Context) -> None:
    await ctx.respond("It worked!")
    
def load(bot: lightbulb.BotApp) -> None:
    # bot.add_plugin(mod_plugin)
    return