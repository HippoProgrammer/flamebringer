import discord
import cogs.private as private
import validators
import datetime
import logging, sys

logger = logging.getLogger(__name__)  # get the logger for this script
logger.setLevel(logging.INFO)

class Automatic(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    halls = discord.SlashCommandGroup("halls", "Commands relating to the Halls of Solaris")

    @halls.command(
        name="vote",
        description="Prepare a vote")
    @discord.option("name",
        description="The name of the proposal going to vote",
        type=discord.SlashCommandOptionType.string)
    @discord.option("primary_author",
        description="The Discord account of the primary author of the proposal",
        type=discord.SlashCommandOptionType.user)
    @discord.option("link",
        description="A link to the text of the proposal",
        type=discord.SlashCommandOptionType.string)
    @discord.option("type",
        description="The type of the proposal",
        type=private.ProposalType)
    @discord.option("duration",
        description="Duration of the poll in hours (default: 48h)",
        required=False,
        type=discord.SlashCommandOptionType.integer)
    @discord.option("secondary_author_1",
        description="The Discord account of a secondary author of the proposal",
        required=False,
        type=discord.SlashCommandOptionType.user)
    @discord.option("secondary_author_2",
        description="The Discord account of another secondary author of the proposal",
        required=False,
        type=discord.SlashCommandOptionType.user)
    @discord.option(
        "secondary_author_3",
        description="The Discord account of a third secondary author of the proposal",
        required=False,
        type=discord.SlashCommandOptionType.user)
    async def vote(self, ctx: discord.ApplicationContext, name: str, primary_author: discord.Member, link: str, type: private.ProposalType, duration: int, secondary_author_1: discord.Member, secondary_author_2: discord.Member, secondary_author_3: discord.Member):
        logger.info(f"Vote command sent by {ctx.user.id}")
        authors = [author for author in [primary_author, secondary_author_1, secondary_author_2, secondary_author_3] if author is not None]
        if isinstance(ctx.channel, discord.threads.Thread):
            permitted = any(ctx.user.get_role(rid) for rid in map(int, private.config[ctx.guild.id]["fw_permission_role_ids"]))
            if permitted:
                logger.info("User is authenticated")
                if duration is None:
                    duration = private.config[ctx.guild.id]["poll_durations"]["default"]
                if duration >= private.config[ctx.guild.id]["poll_durations"]["min"] and duration <= private.config[ctx.guild.id]["poll_durations"]["max"]: # if duration between max and min
                    if validators.url(link):
                        await ctx.defer(ephemeral=True)
                        await private._send_lock_message(ctx=ctx) # if motioning gets implemented this should be spun off to the motioning function
                        await private._set_thread_lock(ctx=ctx)
                        await private._send_image(ctx=ctx, type="header")
                        await private._send_vote_text(ctx=ctx, name=name, authors=authors, type=type, link=link, duration=duration)
                        await private._create_vote_poll(ctx=ctx, name=name, type=type, duration=duration)
                        await private._send_vote_status(ctx=ctx)
                        await private._send_image(ctx=ctx, type="footer")
                        await private._set_tag(ctx=ctx, tag="vote")
                        embed = discord.Embed(title = "Success", description = "The command succeeded.")
                        await ctx.respond(embed = embed, ephemeral=True)
                    else:
                        logger.info("Invalid URL provided: valid URL must be provided")

                        embed = discord.Embed(title = "Invalid URL", description = "The link provided is not a valid URL.")
                        logger.debug("Embed object created")

                        await ctx.respond(embed = embed, ephemeral = True)
                        logger.info("Invalid URL embed sent")
                else:
                    logger.info("Poll duration out of bounds")

                    embed = discord.Embed(title = "Invalid poll duration", description = f"Polls must be between {private.config[ctx.guild.id]["poll_durations"]["min"]} and {private.config[ctx.guild.id]["poll_durations"]["max"]} hours long.")
                    logger.debug("Embed object created")

                    await ctx.respond(embed = embed, ephemeral = True)
                    logger.info("Invalid duration embed sent")
            else:
                logger.info("User is not authenticated")

                embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
                logger.debug("Embed object created")

                await ctx.respond(embed = embed, ephemeral = True)
                logger.info("No permissions embed sent")
        else:
            logger.info("Command is not in a thread channel")

            embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("Wrong channel type embed sent")

    @halls.command(
        name="count",
        description="Edit the vote status when the vote ends")
    @discord.option("name",
        description="Name of the proposal")
    @discord.option("type",
        description="The type of the proposal",
        type=private.ProposalType)
    @discord.option("quorum",
        description="Quorum for the vote (on vote text)",
        type=discord.SlashCommandOptionType.integer,
        min_value=0)
    @discord.option("status_msg",
        description="The URL of the vote status message (sent by the bot) - automatically filled if not given",
        required = None)
    @discord.option("poll_msg",
        description="The URL of the poll (sent by the bot) - automatically filled if not given",
        required = None)
    async def count(self, ctx: discord.ApplicationContext, name: str, type: private.ProposalType, quorum: int, status_msg: discord.Message, poll_msg: discord.Message):
        logger.info(f"Count command sent by {ctx.user.id}")

        if isinstance(ctx.channel, discord.threads.Thread):
            permitted = any(ctx.user.get_role(rid) for rid in map(int, private.config[ctx.guild.id]["fw_permission_role_ids"]))
            if permitted:
                logger.info("User is authenticated")
                if poll_msg is None: # if the poll message has not been provided
                    poll_msg = await private._get_past_message_from_current_thread(ctx=ctx, type='poll') # attempt to fetch automatically
                if status_msg is None:
                    status_msg = await private._get_past_message_from_current_thread(ctx=ctx, type='status')
                if poll_msg is not None and status_msg is not None: # if both have been provided or can be automatically fetched
                    if poll_msg.poll is not None: # do a final check in case this is manually entered
                        if "STATUS" in status_msg.content:
                            if (quorum == 0 and not type.is_legislative) or (quorum >= 7 and type.is_legislative): # quorum must be either zero (non-legislative) or greater than seven (legislative minimum)
                                await ctx.defer(ephemeral=True)
                                await private._edit_vote_status_with_count_and_sanction(ctx=ctx, name=name, status_msg=status_msg, poll_msg=poll_msg, type=type, quorum=quorum)
                                embed = discord.Embed(title = "Success", description = "The command succeeded.")
                                await ctx.respond(embed = embed, ephemeral=True)
                            else:
                                logger.info("Supplied quorum value is out of legal range")

                                embed = discord.Embed(title = "Quorum value invalid", description = "The quorum value must either be zero (non-legislative proposal) or greater than / equal to seven (legislative proposal).")
                                logger.debug("Embed object created")

                                await ctx.respond(embed = embed, ephemeral = True)
                                logger.info("Quorum out of range embed sent")

                        else:
                            logger.info("status_msg does not contain 'STATUS'")

                            embed = discord.Embed(title = "Status Message not provided", description = "The status message does not contain the word 'status' - are you sure it is correct?")
                            logger.debug("Embed object created")

                            await ctx.respond(embed = embed, ephemeral = True)
                            logger.info("'No status' embed sent")
                    else:
                        logger.info("No poll on poll_msg: poll_msg must have poll")

                        embed = discord.Embed(title = "Poll Message does not have poll", description = "A poll must be attached to the poll_msg argument.")
                        logger.debug("Embed object created")

                        await ctx.respond(embed = embed, ephemeral = True)
                        logger.info("'No poll' embed sent")
                else:
                    logger.info("No poll_msg or status_msg: auto fetching must have failed")

                    embed = discord.Embed(title = "Automatic fetching failed", description = f"Automatic fetching of the poll message or status message failed - please provide manually through `poll_msg` and `status_msg`, and report this bug to <@{private.config[ctx.guild.id]["error_ping"]}>.")

                    await ctx.respond(embed = embed, ephemeral = True)
                    logger.info("Auto fetch failure embed sent")
            else:
                logger.info("User is not authenticated")

                embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
                logger.debug("Embed object created")

                await ctx.respond(embed = embed, ephemeral = True)
                logger.info("No permissions embed sent")
        else:
            logger.info("Command is not in a thread channel")

            embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("Wrong channel type embed sent")

    @halls.command(name="acknowledge", description="Acknowledge the beginning of the debate period")
    async def acknowledge(self, ctx: discord.ApplicationContext):
        logger.info(f"Acknowledge command sent by {ctx.user.id}")
        permitted = any(ctx.user.get_role(rid) for rid in map(int, private.config[ctx.guild.id]["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            conclusion = datetime.datetime.now() + datetime.timedelta(hours=int(private.config[ctx.guild.id]["debate_min_duration"]))
            embed = discord.Embed(title = "Debate period acknowledged", description = f"The debate period has begun and will conclude at <t:{int(round(conclusion.timestamp(),0))}:f> (<t:{int(round(conclusion.timestamp(),0))}:R>), after which the proposal may be motioned to vote by any author.")
            await private._set_tag(ctx=ctx, tag="debate")
            await ctx.respond(embed = embed)
        else:
            logger.info("User is not authenticated")

            embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("No permissions embed sent")

    triune = halls.create_subgroup("triune", "Commands pertaining to the Triune Circle's approval of laws")

    @triune.command(name="approve",
        description="Approve or reject a treaty or constitutional amendment")
    @discord.option("name",
        description="Name of the treaty or constitutional amendment", type=discord.SlashCommandOptionType.string)
    @discord.option("type",
        description="The type of the proposal",
        type=private.ProposalType)
    @discord.option("aye",
        description="How many Triune Circle members voted in favor of approval",
        type=discord.SlashCommandOptionType.integer,
        min_value=0,
        max_value=3)
    @discord.option("nay",
        description="How many Triune Circle members voted against approval",
        type=discord.SlashCommandOptionType.integer,
        min_value=0,
        max_value=3)
    @discord.option("abstain",
        description="How many Triune Circle members did not vote",
        type=discord.SlashCommandOptionType.integer,
        default=0,
        min_value=0,
        max_value=2)
    async def approve(self, ctx: discord.ApplicationContext, name: str, type: private.ProposalType, aye: int, nay: int, abstain: int):
        logger.info(f"Approve command sent by {ctx.user.id}")

        if isinstance(ctx.channel, discord.threads.Thread):
            if ctx.user.get_role(int(private.config[ctx.guild.id]["tc_permission_role_id"])):
                logger.info("User is authenticated")
                if type.is_approvable:
                    await ctx.defer(ephemeral=True)
                    await private._send_tc_approval(ctx=ctx, name=name, type=type, aye=aye, nay=nay, abstain=abstain)
                    embed = discord.Embed(title = "Success", description = "The command succeeded.")
                    await ctx.respond(embed = embed, ephemeral=True)
                else:
                    logger.info("Proposal is not approvable")

                    embed = discord.Embed(title = "No Permissions", description = "Only certain proposal types require TC approval. Verify you selected the correct proposal type.")
                    logger.debug("Embed object created")

                    await ctx.respond(embed = embed, ephemeral = True)
                    logger.info("Wrong type embed sent")
            else:
                logger.info("User is not authenticated")

                embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
                logger.debug("Embed object created")

                await ctx.respond(embed = embed, ephemeral = True)
                logger.info("No permissions embed sent")
        else:
            logger.info("Command is not in a thread channel")

            embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("Wrong channel type embed sent")

    manual = halls.create_subgroup("manual", "Commands allowing manual operation of the bot")
    @manual.command(name="poll",
        description="Send a vote poll")
    @discord.option("name",
        description="The name of the proposal going to vote",
        type=discord.SlashCommandOptionType.string)
    @discord.option("type",
        description="The type of the proposal",
        type=private.ProposalType)
    @discord.option("duration",
        description="Duration of the poll in hours (default 48h)",
        type=discord.SlashCommandOptionType.integer,
        required=False)
    async def poll(self, ctx: discord.ApplicationContext, name: str, type: private.ProposalType, duration: int):
        logger.info(f"Manual poll command sent by {ctx.user.id}")

        permitted = any(ctx.user.get_role(rid) for rid in map(int, private.config[ctx.guild.id]["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            if duration is None:
                duration = private.config[ctx.guild.id]["poll_durations"]["default"]
            if duration >= private.config[ctx.guild.id]["poll_durations"]["min"] and duration <= private.config[ctx.guild.id]["poll_durations"]["max"]: # if duration between max and min
                await ctx.defer(ephemeral=True)
                await private._create_vote_poll(ctx=ctx, name=name, type=type, duration=duration)
                embed = discord.Embed(title = "Success", description = "The command succeeded.")
                await ctx.respond(embed = embed, ephemeral=True)
            else:
                logger.info("Poll duration out of bounds")

                embed = discord.Embed(title = "Invalid poll duration", description = f"Polls must be between {private.config[ctx.guild.id]["poll_durations"]["min"]} and {private.config[ctx.guild.id]["poll_durations"]["max"]} hours long.")
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

        permitted = any(ctx.user.get_role(rid) for rid in map(int, private.config[ctx.guild.id]["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            await ctx.defer(ephemeral=True)
            await private._send_image(ctx=ctx, type=type)
            embed = discord.Embed(title = "Success", description = "The command succeeded.")
            await ctx.respond(embed = embed, ephemeral=True)
        else:
            logger.info("User is not authenticated")

            embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("No permissions embed sent")

def setup(bot):
    bot.add_cog(Automatic(bot))
