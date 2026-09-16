import discord
import cogs.private as private
import logging, sys

logger = logging.getLogger(__name__)  # get the logger for this script
logger.setLevel(logging.INFO)

class Manual(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    manual = discord.SlashCommandGroup("manual", "Commands allowing manual operation of the bot")
    @manual.command(name="poll",
        description="Send a vote poll")
    @discord.option("name",
        description="The name of the proposal going to vote",
        type=discord.SlashCommandOptionType.string)
    @discord.option("type",
        description="The type of the proposal",
        type=ProposalType)
    @discord.option("duration",
        description="Duration of the poll in hours (default: 48h)",
        type=discord.SlashCommandOptionType.integer)
    async def poll(self, ctx: discord.ApplicationContext, name: str, type: ProposalType, duration: int):
        logger.info(f"Manual poll command sent by {ctx.user.id}")

        permitted = any(ctx.user.get_role(rid) for rid in map(int, config[ctx.guild.id]["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            if duration is None:
                duration = config[ctx.guild.id]["poll_durations"]["default"]
            if duration >= config[ctx.guild.id]["poll_durations"]["min"] and duration <= config[ctx.guild.id]["poll_durations"]["max"]: # if duration between max and min
                await ctx.defer(ephemeral=True)
                await _create_vote_poll(ctx=ctx, name=name, type=type, duration=duration)
                embed = discord.Embed(title = "Success", description = "The command succeeded.")
                await ctx.respond(embed = embed, ephemeral=True)
            else:
                logger.info("Poll duration out of bounds")

                embed = discord.Embed(title = "Invalid poll duration", description = f"Polls must be between {config[ctx.guild.id]["poll_durations"]["min"]} and {config[ctx.guild.id]["poll_durations"]["max"]} hours long.")
                logger.debug("Embed object created")

                await ctx.respond(embed = embed, ephemeral = True)
                logger.info("Invalid duration embed sent")
        else:
            logger.info("User is not authenticated")

            embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("No permissions embed sent")

    @manual.command(name="image", description="Send an official header or footer image")
    @discord.option("type",
        description="Which image should be provided?",
        type=discord.SlashCommandOptionType.string,
        choices=["header", "footer"])
    async def image(self, ctx: discord.ApplicationContext, type: str):
        logger.info(f"Manual image command sent by {ctx.user.id}")

        permitted = any(ctx.user.get_role(rid) for rid in map(int, config[ctx.guild.id]["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            await ctx.defer(ephemeral=True)
            await _send_image(ctx=ctx, type=type)
            embed = discord.Embed(title = "Success", description = "The command succeeded.")
            await ctx.respond(embed = embed, ephemeral=True)
        else:
            logger.info("User is not authenticated")

            embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("No permissions embed sent")


def setup(bot):
    bot.add_cog(Manual(bot))
