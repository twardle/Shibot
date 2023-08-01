from __future__ import annotations
import os, logging
import hikari
import lightbulb
from lightbulb import context as context_

from shibot import GUILD_ID

__all__ = [
    "ReactionNavigator",
    "ButtonNavigator",
    "ReactionButton",
    "ComponentButton",
    "next_page",
    "prev_page",
    "first_page",
    "last_page",
    "stop",
]

with open("./secrets/token") as f:
    _token = f.read().strip()

bot = lightbulb.BotApp(
    token=_token,
    prefix = "!",
    help_class=None,
    intents=hikari.Intents.ALL,
    default_enabled_guilds=GUILD_ID,
)

bot.load_extensions_from("./shibot/extensions")

if __name__ == "__main__":
    if os.name != "nt":
            import uvloop
            uvloop.install()

    bot.run()