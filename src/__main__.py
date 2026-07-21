# import required libraries
import logging  # log handler
import os # file handling
import sys # stream handling
import discord  # py-cord: discord bot framework
import validators # string validation
import datetime # datetime handling
from yaml import safe_load as load_yaml # yaml parsing
from math import ceil # ceiling function

__version__ = "1.3.5b1"

# configure logging
logger = logging.getLogger("flamewarden")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s") # format [time] - [module] - [error level] - [message]
handler.setFormatter(formatter) # attach the formatter to the handler
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(logging.DEBUG)  # set the logs to output at debug verbosity
logger.info("Logging started")

# load config
config_file = str(os.getenv("FLAMEBRINGER_CONFIG_FILE")) # get the config file path from the env var
if not os.path.isfile(config_file): # check the config file actually exists: if not,
    logger.error("FLAMEBRINGER_CONFIG_FILE environment variable is not a valid path, cannot start" ) # send an error message
    sys.exit() # quit
# if we get here, the config file must exist, so we
with open(config_file, "r") as file: # open the config file
    config = load_yaml(file) # parse it into a python object
config = config["config"] # navigate into the first section - everything should be under this first key so we don't need to constantly reference it
logger.info("Config loaded")

# load token
token_file = config["token_file"] # get the token file path from the config file
if not os.path.isfile(token_file): # check the token file actually exists: if not,
    logger.error("token_file configuration value is not a valid path, cannot start") # send an error message
    sys.exit() # quit
# if we get here, the token file must exist, so we
with open(token_file, "r") as file: # read the token file
    token = file.read()
logger.info('Token loaded')

# create the Bot object
intents = discord.Intents.default() # we need default intents so the bot actually functions well
intents.members = True # we also need members permission to calculate quorum, as that requires fetching the full member list of a role which needs the members intent
bot = discord.Bot(intents = intents)  # create a bot instance, with the previously set intents
logger.debug("Bot object created")

# basic discord functions (calculate quorum, lock threads, set tags etc.)
async def _get_quorum(ctx: discord.ApplicationContext): # get quorum based on a pre-configured role
    quorum_role = ctx.guild.get_role(int(config["quorum_role_id"])) # fetch the role id from the config and get the Role object from the bot
    count = len([member for member in quorum_role.members if not(member.bot)]) # use a list comprehension to only count members who are not bots
    count_quorum = ceil(count / 10) # quorum is 10%, rounded up
    quorum = max(count_quorum, 7) # but if 10% is less than 7, we use 7
    return quorum

async def _set_tag(ctx: discord.ApplicationContext, tag:str): # set a tag on a thread, CLEARING ALL PREVIOUS TAGS
    if isinstance(ctx.channel, discord.threads.Thread): # check that the channel is actually a thread channel
        if isinstance(ctx.channel.parent, discord.ForumChannel): # check that the thread channel is in a forum channel, so it actually supports tags
            tag = ctx.channel.parent.get_tag(config[f"{tag}_tag_id"]) # if those are both true, try to get the requested ForumTag object from the parent forum channel
            await ctx.channel.edit(applied_tags=[tag]) # apply that tag to the thread

async def _set_thread_lock(ctx: discord.ApplicationContext, lock = True): # lock or unlock a thread
    if isinstance(ctx.channel, discord.threads.Thread): # if it's a thread, it can be locked or unlocked
        await ctx.channel.edit(locked=lock) # so set the status requested

# basic python functions (string formatting etc.)
async def _format_definite_article(name: str): # format a name to have correct definite article (the)
    if "the" in name.lower(): # if 'the' is in the name
        the_name = name # the name should be "the [x]"
    else: # otherwise
        the_name = f"the {name}" # the name should be the "[x]"
    return the_name

# command backend functions
# halls commands
async def _send_lock_message(ctx: discord.ApplicationContext):
    await ctx.channel.send(f"<@&{config['fw_primary_role_id']}> **The Office of the Flamewarden acknowledges the motion and second(s) and shall promptly schedule a vote.**")

async def _send_vote_status(ctx: discord.ApplicationContext):
    await ctx.channel.send("## __STATUS__: AT VOTE")

async def _send_image(ctx: discord.ApplicationContext, header:bool):
    if header:
        with open(config["image_paths"]["header"], "rb") as image:
            file = discord.File(fp=image, filename="fw_header.png", description="Seal of the Office of the Flamewarden")
    else:
        with open(config["image_paths"]["footer"], "rb") as image:
            file = discord.File(fp=image, filename="fw_footer.png", description="Banner of the Office of the Flamewarden")
    await ctx.channel.send(file=file)

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
            await _set_thread_lock(ctx=ctx, lock=False)

    tc_approval = f"**{the_name.title()}** has been **{status}** by the Triune Circle ({aye}-{nay})."

    for id in config["fw_announcement_role_ids"]:
        tc_approval = f"<@&{id}> " + tc_approval # append a ping of every role in fw_announcement_role_ids to the beginning of the tc_approval string

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
        aye_percent = (aye / vote_total)
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
    status = f"## __STATUS__: {passed}\n\n- Aye: {aye}\n- Nay: {nay}\n- Abstain: {abstain}\n\nTotal votes cast: {vote_total}\n\nAye = {round(aye_percent * 100, 1)}%"
    await status_msg.edit(content=status)
    await ctx.channel.send(content=sanction)
    if passed == "PASSED" or passed == "APPROVED":
        await _set_tag(ctx=ctx, tag="passed")
    elif passed == "FAILED" or passed == "REJECTED":
        await _set_tag(ctx=ctx, tag="failed")

async def _send_vote_text(ctx: discord.ApplicationContext, name: str, author: discord.Member, constitutional: bool, treaty: bool, legislative: bool, link: str, duration: int):
    the_name = await _format_definite_article(name=name)
    quorum = await _get_quorum(ctx=ctx)
    if constitutional:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE CONSTITUTIONAL AMENDMENT]({link})\n\n**__Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the amendment\n\n- **Nay** – Opposed to the amendment\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "66,6"
    elif treaty:
        header = f"## VOTING: {the_name.upper()} (TREATY)\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE TREATY]({link})\n\n**__Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the signing of the treaty\n\n- **Nay** – Opposed to the signing of the treaty\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    else:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by <@{author.id}> is now at vote.\n\n**__Proposal__**:\n[LINK TO THE BILL]({link})\n\n**__Discussion__**:\n[LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the bill\n\n- **Nay** – Opposed to the bill\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    if legislative:
        footer = f"The voting period will last __{duration} hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a {majority}% majority of Aye votes to pass. Abstain votes are registered but not counted. The quorum for this vote is **{quorum}** (10% of Starborn)."
    else:
        footer = f"The voting period will last __{duration} hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a {majority}% majority of Aye votes to pass. Abstain votes are registered but not counted. There is **no quorum** for this vote."
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

# bot events
@bot.event
async def on_ready() -> None:
    activity = discord.Game("Warding the Flame...")
    status = discord.Status.online
    await bot.change_presence(activity=activity, status=status)
    logger.info("Bot started, ready for interaction")

@bot.event
async def on_application_command_error(ctx:discord.ApplicationContext, error:discord.DiscordException): # error handler
    if type(error) is discord.ext.commands.MessageNotFound:
        logger.info("Message was not found")

        embed = discord.Embed(title = "Message not Found", description = "The message provided was not found.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Message not found embed sent")
    else:
        logger.error(error, stack_info = True, exc_info = True)
        await ctx.channel.send(f'<@{config["error_ping"]}> An unspecified error occurred.')

# slash commands
@bot.slash_command(name="info", description="Information about the bot")
async def info(ctx: discord.ApplicationContext) -> None:
    logger.info(f"Info command sent by {ctx.user.id}")
    embed = discord.Embed(title = f"Flamebringer v{__version__}", description = f"For help or technical support message <@{config['error_ping']}> on Discord.")
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
@discord.option("legislative", description="Is the proposal a legislative proposal? (this does not include Honorary Titles)", type=discord.SlashCommandOptionType.boolean, default=True)
@discord.option("duration", description="Duration of the poll in hours (default: 48h)", type=discord.SlashCommandOptionType.integer, min_value=config["poll_durations"]["min"], max_value=config["poll_durations"]["max"], default=config["poll_durations"]["default"])
async def vote(ctx: discord.ApplicationContext, name: str, author: discord.Member, link: str, treaty: bool, constitutional: bool, legislative: bool, duration: int):
    logger.info(f"Vote command sent by {ctx.user.id}")

    if isinstance(ctx.channel, discord.threads.Thread):
        permitted = any(ctx.user.get_role(rid) for rid in map(int, config["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")
            if validators.url(link):
                if not (constitutional and treaty):
                    await ctx.defer(ephemeral=True)
                    await _send_lock_message(ctx=ctx) # if motioning gets implemented this should be spun off to the motioning function
                    await _set_thread_lock(ctx=ctx)
                    await _send_image(ctx=ctx, header=True)
                    await _send_vote_text(ctx=ctx, name=name, author=author, constitutional=constitutional, treaty=treaty, legislative=legislative, link=link, duration=duration)
                    await _create_vote_poll(ctx=ctx, name=name, treaty=treaty, duration=duration)
                    await _send_vote_status(ctx=ctx)
                    await _send_image(ctx=ctx, header=False)
                    await _set_tag(ctx=ctx, tag="vote")
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
    else:
        logger.info("Command is not in a thread channel")

        embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Wrong channel type embed sent")

@halls.command(name="count", description="Edit the vote status when the vote ends")
@discord.option("name", description="Name of the proposal")
@discord.option("status_msg", description="The URL of the vote status message (sent by the bot)")
@discord.option("poll_msg", description="The URL of the poll (sent by the bot)")
@discord.option("constitutional", description="Is the proposal a constitutional amendment?", type=discord.SlashCommandOptionType.boolean)
@discord.option("treaty", description="Is the proposal a treaty?", type=discord.SlashCommandOptionType.boolean)
@discord.option("quorum", description="Quorum for the vote (on vote text)", type=discord.SlashCommandOptionType.integer, min_value=0)
async def count(ctx: discord.ApplicationContext, name: str, status_msg: discord.Message, poll_msg: discord.Message, constitutional:bool, treaty: bool, quorum: int):
    logger.info(f"Count command sent by {ctx.user.id}")

    if isinstance(ctx.channel, discord.threads.Thread):
        permitted = any(ctx.user.get_role(rid) for rid in map(int, config["fw_permission_role_ids"]))
        if permitted:
            logger.info("User is authenticated")

            if not (constitutional and treaty):
                if poll_msg.poll is not None:
                    if "STATUS" in status_msg.content:
                        if quorum == 0 or quorum >= 7: # quorum must be either zero (non-legislative) or greater than seven (legislative minimum)
                            await ctx.defer(ephemeral=True)
                            await _edit_vote_status_with_count_and_sanction(ctx=ctx, name=name, status_msg=status_msg, poll_msg=poll_msg, constitutional=constitutional, treaty=treaty, quorum=quorum)
                            await ctx.respond(content="Success", ephemeral=True)
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
    else:
        logger.info("Command is not in a thread channel")

        embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Wrong channel type embed sent")

triune = halls.create_subgroup("triune", "Commands pertaining to the Triune Circle's approval of laws")

@triune.command(name="approve", description="Approve or reject a treaty or constitutional amendment")
@discord.option("name", description="Name of the treaty or constitutional amendment", type=discord.SlashCommandOptionType.string)
@discord.option("treaty", description="Is the bill a treaty? (if not, it is a constitutional amendment)", type=discord.SlashCommandOptionType.boolean)
@discord.option("aye", description="How many Triune Circle members voted in favor of approval", type=discord.SlashCommandOptionType.integer, min_value=0, max_value=3)
@discord.option("nay", description="How many Triune Circle members voted against approval", type=discord.SlashCommandOptionType.integer, min_value=0, max_value=3)
async def approve(ctx: discord.ApplicationContext, name: str, treaty: bool, aye: int, nay: int):
    logger.info(f"Approve command sent by {ctx.user.id}")

    if isinstance(ctx.channel, discord.threads.Thread):
        if ctx.user.get_role(int(config["tc_permission_role_id"])):
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
    else:
        logger.info("Command is not in a thread channel")

        embed = discord.Embed(title = "Wrong Channel Type", description = "Halls commands must be run in a thread.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Wrong channel type embed sent")

@bot.event
async def on_application_command_error(ctx:discord.ApplicationContext, error:discord.DiscordException):
    if type(error) is discord.ext.commands.MessageNotFound:
        logger.info("Message was not found")

        embed = discord.Embed(title = "Message not Found", description = "The message provided was not found.")
        logger.debug("Embed object created")

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info("Message not found embed sent")
    else:
        logger.error(error, stack_info = True, exc_info = True)
        await ctx.channel.send(f'<@{config["error_ping"]}> An unspecified error occurred.')

bot.run(token)
