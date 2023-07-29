import hikari
import lightbulb
import pytz
from datetime import datetime, timedelta

mod_plugin = lightbulb.Plugin("Purge")

@mod_plugin.command
@lightbulb.app_command_permissions(hikari.Permissions.MANAGE_MESSAGES, dm_enabled=False)
@lightbulb.add_checks(
    lightbulb.bot_has_guild_permissions(hikari.Permissions.MANAGE_MESSAGES),
)
@lightbulb.option(
    "sent_by",
    "Only purge messages sent by this user.",
    type=hikari.User,
    required=False,
)
@lightbulb.option(
    "messages",
    "The number of messages to purge.",
    type=int,
    required=False,
    min_value=2,
    max_value=200,
    default=5,
)
@lightbulb.command("purge", "Purge messages.", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def purge_messages(ctx: lightbulb.Context) -> None:
    num_msgs = ctx.options.messages
    sent_by = ctx.options.sent_by
    channel = ctx.channel_id

    bulk_delete_limit = datetime.now().replace(tzinfo=pytz.UTC) - timedelta(days=14)

    iterator = (
        ctx.bot.rest.fetch_messages(channel)
        .take_while(lambda msg: msg.created_at > bulk_delete_limit)
        .filter(lambda msg: not (msg.flags & hikari.MessageFlag.LOADING))
    )
    if sent_by:
        iterator = iterator.filter(lambda msg: msg.author.id == sent_by.id)

    iterator = iterator.limit(num_msgs)

    count = 0

    async for messages in iterator.chunk(100):
        count += len(messages)
        await ctx.bot.rest.delete_messages(channel, messages)

    await ctx.respond(f"{count} messages deleted.", delete_after=5)

@purge_messages.set_error_handler
async def on_purge_error(event: lightbulb.CommandErrorEvent) -> bool:
    exception = event.exception.__cause__ or event.exception

    if isinstance(exception, lightbulb.BotMissingRequiredPermission):
        await event.context.respond("I do not have permission to delete messages.")
        return True

    return False

def load(bot: lightbulb.BotApp) -> None:
    # bot.add_plugin(mod_plugin)
    return