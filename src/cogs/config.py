import discord
from cogs.private import *
import sys
sys.path.append('../')
from __main__ import __version__
import logging

logger = logging.getLogger("flamebringer")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s") # format [time] - [module] - [error level] - [message]
handler.setFormatter(formatter) # attach the formatter to the handler
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(logging.INFO)

class Config(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @bot.slash_command(name="info", description="Information about the bot")
    async def info(ctx: discord.ApplicationContext) -> None:
        logger.info(f"Info command sent by {ctx.user.id}")
        embed = discord.Embed(title = f"Flamebringer v{__version__}", description = f"For help or technical support message <@{config['error_ping']}> on Discord.")
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Info embed sent')

def setup(bot):
    bot.add_cog(Config(bot))