# import required libraries
import logging  # log handler
import os
import sys
import discord  # py-cord: discord bot framework
import validators
import datetime
from yaml import safe_load as load_yaml
from math import ceil

logger = logging.getLogger("assembly")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(logging.DEBUG)  # set the logs to output at debug verbosity
logger.info("Logging started")

config_file = str(os.getenv("FLAMEBRINGER_CONFIG_FILE"))
if not os.path.isfile(config_file): # check the config file actually exists
    msg = "FLAMEBRINGER_CONFIG_FILE environment variable is not a valid path, cannot start"
    logger.error(msg)
    sys.exit()

# read config file
with open(config_file, "r") as file:
    config = load_yaml(file)
config = config["config"]
logger.info("Config loaded")

with open(config["token_file"], "r") as file: # read the token file
    token = file.read()
logger.info('Token loaded')

# create the Bot object
bot = discord.Bot()  # create a bot instance
logger.debug("Bot object created")

async def _get_quorum(ctx: discord.ApplicationContext):
    quorum_role = await ctx.guild.fetch_role(int(config["quorum_role_id"]))
    count = len(quorum_role.members)
    count_quorum = ceil(count / 10)
    quorum = max(count_quorum, 7)
    return quorum

async def _format_definite_article(name: str):
    if "the" in name.lower():
        the_name = name
    else:
        the_name = f"the {name}"
    return the_name

async def _send_tc_approval(ctx: discord.ApplicationContext, name: str, treaty: bool, aye: int, nay: int):
    the_name = await _format_definite_article(name=name)

    if aye > nay:
        status = "approved"
        if treaty:
            fw_approval = f"**{the_name.title()} has passed the Halls of Solaris and has been approved by the Triune Circle. As of <t:{int(round(datetime.datetime.now().timestamp(),0))}:f> it is now formally ratified.**"
        else:
            fw_approval = f"**{the_name.title()} has passed the Halls of Solaris and has been approved by the Triune Circle. As of <t:{int(round(datetime.datetime.now().timestamp(),0))}:f> it is now formally adopted into the Constitution.**"
    else:
        status = "rejected"
        if treaty:
            fw_approval = f"**{the_name.title()} has been vetoed by the Triune Circle.**"
        else:
            fw_approval = f"**{the_name.title()} has been vetoed by the Triune Circle. A petition to override the veto may now be submitted within 72 hours in this channel. The petition must receive the support of at least five Starborn, including the original proposer, to proceed.**"
    tc_approval = f"**{the_name.title()}** has been **{status}** by the Triune Circle ({aye}-{nay})."

    await ctx.channel.send(content=tc_approval)
    await ctx.channel.send(content=fw_approval)

async def _send_vote_status(ctx: discord.ApplicationContext):
    await ctx.channel.send("## __STATUS__: AT VOTE")

async def _edit_vote_status_with_count_and_sanction(ctx: discord.ApplicationContext, name:str, status_msg:discord.Message, poll_msg:discord.Message, constitutional:bool, treaty:bool, quorum: int):
    the_name = await _format_definite_article(name=name)

    poll = poll_msg.poll
    aye = [answer for answer in poll.answers if answer.text == "Aye"][0].count
    nay = [answer for answer in poll.answers if answer.text == "Nay"][0].count
    abstain = [answer for answer in poll.answers if answer.text == "Abstain"][0].count
    vote_total = aye + nay
    quorum_total = aye + nay + abstain
    if vote_total > 0: # check for div/0 errors!
        aye_percent = (aye / vote_total) * 100
    else:
        aye_percent = 0

    if quorum_total > quorum:
        if constitutional:
            if aye_percent > (2/3):
                passed = "APPROVED"
                sanction = f"**{the_name.title()} has passed the Halls of Solaris, meeting the required two-thirds majority.\nThe amendment is submitted to the <@&{config['tc_permission_role_id']}> who has now 72 hours to formally approve or veto it. Once approval is granted or if no action is taken within that timeframe, it will become law.**"
            else:
                passed = "REJECTED"
                sanction = f"**{the_name.title()} has failed to achieve the required two-thirds majority and therefore does not pass the Halls of Solaris.**"
        elif treaty:
            if aye_percent > (3/5):
                passed = "APPROVED"
                sanction = f"**{the_name.title()} has been approved by the Halls of Solaris. <@&{config['tc_permission_role_id']}>**"
            else:
                passed = "REJECTED"
                sanction = f"**{the_name.title()} has been rejected by the Halls of Solaris.**"
        else:
            if aye_percent > (3/5):
                passed = "PASSED"
                sanction = f"**{the_name.title()} has been passed by the Halls of Solaris and as of <t:{int(round(datetime.datetime.now().timestamp(),0))}:f> it is now law.**"
            else:
                passed = "FAILED"
                sanction = f"**{the_name.title()} has failed to achieve the required majority and therefore does not pass the Halls of Solaris.**"
    else:
        passed = f"FAILED TO REACH QUORUM\n*The quorum for this vote was {quorum}, but only {quorum_total} Starborn participated.*"
        sanction = f"**{the_name.title()} has failed to reach quorum and therefore does not pass the Halls of Solaris. The Flamewarden may reopen debate or extend the voting period.**"
    status = f"## __STATUS__: {passed}\n\n- Aye: {aye}\n- Nay: {nay}\n- Abstain: {abstain}\n\nTotal votes cast: {vote_total}\n\nAye = {round(aye_percent, 1)}%"
    await status_msg.edit(content=status)
    await ctx.channel.send(content=sanction)

async def _send_image(ctx: discord.ApplicationContext, header:bool):
    if header:
        with open(config["image_paths"]["header"], "rb") as image:
            file = discord.File(fp=image, filename="fw_header.png", description="Seal of the Office of the Flamewarden")
    else:
        with open(config["image_paths"]["footer"], "rb") as image:
            file = discord.File(fp=image, filename="fw_footer.png", description="Banner of the Office of the Flamewarden")
    await ctx.channel.send(file=file)

async def _send_vote_text(ctx: discord.ApplicationContext, name: str, author: discord.Member, constitutional: bool, treaty: bool, link: str, duration: int):
    the_name = await _format_definite_article(name=name)
    quorum = await _get_quorum(ctx=ctx)
    if constitutional:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE CONSTITUTIONAL AMENDMENT]({link})\n\n**__ Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the amendment\n\n- **Nay** – Opposed to the amendment\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "66,6"
    elif treaty:
        header = f"## VOTING: {the_name.upper()} (TREATY)\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE TREATY]({link})\n\n**__ Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the signing of the treaty\n\n- **Nay** – Opposed to the signing of the treaty\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    else:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE BILL]({link})\n\n**__ Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the bill\n\n- **Nay** – Opposed to the bill\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    footer = f"The voting period will last __{duration} hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a {majority}% majority of Aye votes to pass. Abstain votes are registered but not counted. The quorum for this vote is **{quorum}** (10% of Starborn)."
    text = header + footer
    await ctx.channel.send(content=text)

async def _create_vote_poll(ctx: discord.ApplicationContext, name: str, treaty: bool, duration: int):
    the_name = await _format_definite_article(name=name)
    if treaty:
        title = f'Shall the Halls of Solaris approve the signing of {the_name}?'
    else:
        title = f'Shall the Halls of Solaris pass {the_name}?'
    options = [
        discord.PollAnswer(text="Aye", emoji="✅"),
        discord.PollAnswer(text="Nay", emoji="❌"),
        discord.PollAnswer(text="Abstain", emoji="🔄")
    ]
    poll = discord.Poll(question=title, answers=options, duration=duration)
    await ctx.channel.send(poll=poll)

@bot.event
async def on_ready() -> None:
    activity = discord.Game("Warding the Flame...")
    status = discord.Status.online
    await bot.change_presence(activity=activity, status=status)
    logger.info("Bot started, ready for interaction")

# create info slash command
@bot.slash_command(name="info", description="Information about the bot")
async def info(ctx: discord.ApplicationContext) -> None:
    embed = discord.Embed(title = "Flamebringer v1.2.0", description = f"For help or technical support message <@{config['error_ping']}> on Discord.")
    logger.debug('Embed object created')

    await ctx.respond(embed = embed, ephemeral = True)
    logger.info('Info embed sent')

halls = bot.create_group("halls", "Commands relating to the Halls of Solaris")

@halls.command(name="vote", description="Prepare a vote")
@discord.option("name", description="The name of the proposal going to vote", type=discord.SlashCommandOptionType.string)
@discord.option("author", description="The Discord account of the author of the proposal")
@discord.option("link", description="A link to the text of the proposal", type=discord.SlashCommandOptionType.string)
@discord.option("treaty", description="Is the proposal a treaty?", type=discord.SlashCommandOptionType.boolean)
@discord.option("constitutional", description="Is the proposal a constitutional amendment?", type=discord.SlashCommandOptionType.boolean)
@discord.option("duration", description="Duration of the poll in hours (default: 48h)", type=discord.SlashCommandOptionType.integer, min_value=config["poll_durations"]["min"], max_value=config["poll_durations"]["max"], default=config["poll_durations"]["default"])
async def vote(ctx: discord.ApplicationContext, name: str, author: discord.Member, link: str, treaty: bool, constitutional: bool, duration: int):
    logger.info("Vote command sent")

    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in config["fw_permission_role_ids"]]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break

    if permitted:
        logger.info("User is authenticated")
        if validators.url(link):
            if not (constitutional and treaty):
                await ctx.defer(ephemeral=True)
                await _send_image(ctx=ctx, header=True)
                await _send_vote_text(ctx=ctx, name=name, author=author, constitutional=constitutional, treaty=treaty, link=link, duration=duration)
                await _create_vote_poll(ctx=ctx, name=name, treaty=treaty, duration=duration)
                await _send_vote_status(ctx=ctx)
                await _send_image(ctx=ctx, header=False)
                await ctx.respond(content="Success", ephemeral=True)
            else:
                logger.info("Conflicting options selected: bill cannot be both constitutional and treaty")

                embed = discord.Embed(title = "Bill Type Mismatch", description = "The bill cannot be both a constitutional amendment and a treaty.")
                logger.debug("Embed object created")

                await ctx.respond(embed = embed, ephemeral = True)
                logger.info("Bill type mismatch embed sent")
        else:
            logger.info("Invalid URL provided: valid URL must be provided")

            embed = discord.Embed(title = "Invalid URL", description = "The link provided is not a valid URL.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("Invalid URL embed sent")
    else:
        logger.info("User is not authenticated")

        embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("No permissions embed sent")

@halls.command(name="count", description="Edit the vote status when the vote ends")
@discord.option("name", description="Name of the proposal")
@discord.option("status_msg", description="The URL of the vote status message (sent by the bot)")
@discord.option("poll_msg", description="The URL of the poll (sent by the bot)")
@discord.option("constitutional", description="Is the proposal a constitutional amendment?", type=discord.SlashCommandOptionType.boolean)
@discord.option("treaty", description="Is the proposal a treaty?", type=discord.SlashCommandOptionType.boolean)
@discord.option("quorum", description="Quorum for the vote (on vote text)", type=discord.SlashCommandOptionType.integer, min_value=7)
async def count(ctx: discord.ApplicationContext, name: str, status_msg: discord.Message, poll_msg: discord.Message, constitutional:bool, treaty: bool, quorum: int):
    logger.info("Count command sent")

    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in config["fw_permission_role_ids"]]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break

    if permitted:
        logger.info("User is authenticated")

        if not (constitutional and treaty):
            if poll_msg.poll is not None:
                if "STATUS" in status_msg.content:
                    await ctx.defer(ephemeral=True)
                    await _edit_vote_status_with_count_and_sanction(ctx=ctx, name=name, status_msg=status_msg, poll_msg=poll_msg, constitutional=constitutional, treaty=treaty, quorum=quorum)
                    await ctx.respond(content="Success", ephemeral=True)
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
            logger.info("Conflicting options selected: bill cannot be both constitutional and treaty")

            embed = discord.Embed(title = "Bill Type Mismatch", description = "The bill cannot be both a constitutional amendment and a treaty.")
            logger.debug("Embed object created")

            await ctx.respond(embed = embed, ephemeral = True)
            logger.info("Bill type mismatch embed sent")
    else:
        logger.info("User is not authenticated")

        embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("No permissions embed sent")

triune = halls.create_subgroup("triune", "Commands pertaining to the Triune Circle's approval of laws")

@triune.command(name="approve", description="Approve or reject a treaty or constitutional amendment")
@discord.option("name", description="Name of the treaty or constitutional amendment", type=discord.SlashCommandOptionType.string)
@discord.option("treaty", description="Is the bill a treaty? (if not, it is a constitutional amendment)", type=discord.SlashCommandOptionType.boolean)
@discord.option("aye", description="How many Triune Circle members voted in favor of approval", type=discord.SlashCommandOptionType.integer, min_value=0, max_value=3)
@discord.option("nay", description="How many Triune Circle members voted against approval", type=discord.SlashCommandOptionType.integer, min_value=0, max_value=3)
async def approve(ctx: discord.ApplicationContext, name: str, treaty: bool, aye: int, nay: int):
    logger.info("Approve command sent")

    permitted_role = await ctx.guild.fetch_role(int(config["tc_permission_role_id"]))
    if permitted_role in ctx.user.roles:
        logger.info("User is authenticated")
        await ctx.defer(ephemeral=True)
        await _send_tc_approval(ctx=ctx, name=name, treaty=treaty, aye=aye, nay=nay)
        await ctx.respond(content="Success", ephemeral=True)
    else:
        logger.info("User is not authenticated")

        embed = discord.Embed(title = "No Permissions", description = "You do not have the required permissions to run this command.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("No permissions embed sent")

@bot.event
async def on_application_command_error(ctx:discord.ApplicationContext, error:discord.DiscordException):
    if type(error) is discord.ext.commands.MessageNotFound:
        logger.info("Message was not found")

        embed = discord.Embed(title = "Message not Found", description = "The message provided was not found.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Message not found embed sent")
    else:
        logger.exception(error)
        await ctx.channel.send(f'<@{config["error_ping"]}> An unspecified error occurred.')

bot.run(token)
