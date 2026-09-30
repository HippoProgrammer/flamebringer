import discord
import cogs.private as private
import sys
sys.path.append('../')
from __main__ import __version__
import logging

logger = logging.getLogger(__name__)  # get the logger for this script
logger.setLevel(logging.INFO)

class Config(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="info", description="Information about the bot")
    async def info(self, ctx: discord.ApplicationContext) -> None:
        logger.info(f"Info command sent by {ctx.user.id}")
        embed = discord.Embed(title = f"Flamebringer v{__version__}", description = f"For help or technical support message <@{private.config[ctx.guild.id]['error_ping']}> on Discord.")
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Info embed sent')

def setup(bot):
    bot.add_cog(Config(bot))
