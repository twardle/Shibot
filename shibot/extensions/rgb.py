import hikari
import lightbulb
from hikari.api.special_endpoints import MessageActionRowBuilder
from hikari.components import ButtonStyle
import typing as t

mod_plugin = lightbulb.Plugin("RGB")

HELP_MESSAGE = """
***Commands Available:***
In order to see the commands under these groups include `-help` or `-h` infront of the group words. 
> `Auctions`,`as`- All commands relating to auctions.
> `Mod`,`m` - All commands relating to mod actions.
> `Auctioneer`,`a` - All commands relating to auctioneer commands. 
"""

COLORS: t.Mapping[str, t.Tuple[int, str]] = {
    "Help": (0xFF0000,HELP_MESSAGE,),
    "Green": (0x00FF00,"Plants green color help them use photosynthesis!",),
    "Blue": (0x0000FF,"Globally, blue is the most common favorite color!",),
    "Orange": (0xFFA500, "The color orange is named after its fruity counterpart, the orange!"),
    "Purple": (0xA020F0,"Purple is the hardest color for human eyes to distinguish!",),
    "Yellow": (0xFFFF00,"Taxi's and school buses are yellow because it's so easy to see!",),
    "Black": (0x000000, "Black is a color which results from the absence of visible light!"),
    "White": (0xFFFFFF, "White objects fully reflect and scatter all visible light!"),
}

async def generate_rows(bot: lightbulb.BotApp, dict) -> t.Iterable[MessageActionRowBuilder]:

    rows: t.List[MessageActionRowBuilder] = []

    row = bot.rest.build_message_action_row()

    for i in range(len(dict)):
        if i % 4 == 0 and i != 0:
            rows.append(row)
            row = bot.rest.build_message_action_row()

        label = list(dict)[i]

        row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            label,
            label=label,
            is_disabled=False,
        )

    rows.append(row)

    return rows


async def handle_responses(bot: lightbulb.BotApp,author: hikari.User,message: hikari.Message, dict, footer, ) -> None:
    with bot.stream(hikari.InteractionCreateEvent, 120).filter(
        
        lambda e: (isinstance(e.interaction, hikari.ComponentInteraction) and e.interaction.user == author and e.interaction.message == message)
    ) as stream:
        async for event in stream:
            cid = event.interaction.custom_id
            print(cid)
            embed = hikari.Embed(title=cid,color=dict[cid][0],description=dict[cid][1],)
            if footer : embed.set_footer(footer)
            try:
                await event.interaction.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE,embed=embed)
            except hikari.NotFoundError:
                await event.interaction.edit_initial_response(embed=embed,)

    await message.edit(components=[])
    

@mod_plugin.command
@lightbulb.command("rgb", "Get facts on different colors!")
@lightbulb.implements(lightbulb.SlashCommand)
async def rgb_command(ctx: lightbulb.Context) -> None:
    """Get facts on different colors!"""
    rows = await generate_rows(ctx.bot, COLORS)
    response = await ctx.respond(hikari.Embed(title="Pick a color"),components=rows,flags=hikari.MessageFlag.EPHEMERAL)
    message = await response.message()
    footer = None
    await handle_responses(ctx.bot, ctx.author, message, COLORS, footer)
    
def load(bot: lightbulb.BotApp) -> None:
    # bot.add_plugin(mod_plugin)
    return