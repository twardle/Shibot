import hikari
import lightbulb

mod_plugin = lightbulb.Plugin("Help")

@mod_plugin.command
@lightbulb.command("help", "Gets help for bot commands",aliases=["Help","h"])
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def help(ctx: lightbulb.Context) -> None:
    await ctx.respond("")

@help.child
@lightbulb.command("h","Gets help info for bot commands")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def embed_command(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="***Commands Available:***",color="#949fe6")
    embed.add_field("> `Auctions`,`as`", "All commands relating to auctions.")
    embed.add_field("> `Mod`,`m`", "All commands relating to mod actions.")
    embed.add_field("> `Auctioneer`,`a`", "All commands relating to auctioneer commands. ")
    embed.set_footer("In order to see the commands under these groups include `-help` or `-h` infront of the group words. ")
    await ctx.respond(embed)
    
@help.child
@lightbulb.command("mod","Gets help info for mod commands",aliases=["mod","m"])
@lightbulb.implements(lightbulb.SlashSubCommand)
async def embed_command(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="Commands used by Mods",color="#949fe6")
    embed.add_field("Warning Related Commands","`.warn`- Warns a member. `.warned` - lets admins know you've warned someone.")
    embed.add_field("Muting Related Commands","`.mute`- Mutes a member. `.unmute`- Unmutes a member.")
    embed.add_field("Other Commands","`.kick`- Kicks a member. `=role`- Adds roles to member")
    embed.set_footer("Message Admins if you need more help.")
    await ctx.respond(embed)

@help.child
@lightbulb.command("auctioneer", "Gets help info for auctioneer commands",aliases=["auctioneer","a"])
@lightbulb.implements(lightbulb.SlashSubCommand)
async def embed_command(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="Commands used by Auctioneers",color= "#949fe6")
    embed.add_field("Balance Command","`.bal [$]`- Include the amount the object was sold for inside the []'s but do not include them in the command")
    embed.add_field("Auction Command","`/auction create `- This will trigger a pop up that you will need to fill in. Make sure to include the correct information")
    embed.add_field("Auction Edit Command","`/auction edit `- Do this in the lot that something needs fixing in. Select the correct option when the pop up appears.")
    embed.set_image("https://media.discordapp.net/attachments/999463438839468073/1061762213104320652/bandicam_2023-01-08_16-43-47-257.jpg?width=720&height=237")
    embed.set_footer("Message Mods/Admins if you need more help")
    await ctx.respond(embed)
    
@help.child
@lightbulb.command("auctions", "Gets help info for auction commands",aliases=["auctions","as"])
@lightbulb.implements(lightbulb.SlashSubCommand)
async def embed_command(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="Commands used in relations to auctions",color= "#949fe6")
    embed.add_field("Claiming Reward Command","`-ticket open [IGN]`- Include your In-Game-Name for inside the []'s but do not include the []'s in the command")
    embed.add_field("Bidding Command","`/bid [$] `- Include the amount you wish to bid inside the []'s but do not include the []'s in the command")
    embed.set_footer("Message Staff if you need more help!")
    await ctx.respond(embed)
    
def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(mod_plugin)