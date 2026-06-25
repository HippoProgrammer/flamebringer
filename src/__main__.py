# import required libraries
import logging  # log handler
import os
import sys
import discord  # py-cord: discord bot framework
from yaml import safe_load as load_yaml

logger = logging.getLogger("assembly")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(logging.DEBUG)  # set the logs to output at debug verbosity
logger.info("Logging started")

config_file = str(os.getenv("FLAMEBRINGER_CONFIG_FILE"))
if not os.path.isfile(config_file):
    msg = "FLAMEBRINGER_CONFIG_FILE environment variable is not a valid path, cannot start"
    logger.error(msg)
    raise Exception(msg)
# read config file
with open(config_file, "r") as file:
    config = load_yaml(file)
permitted_role_ids = config["config"]["permission_role_ids"]
poll_durations = config["config"]["poll_durations"]
error_ping = config["config"]["error_ping"]
image_paths = config["config"]["image_paths"]
token_file = config["config"]["token_file"]

with open(token_file, "r") as file:
    token = file.read()

# create the Bot object
bot = discord.Bot()  # create a bot instance
logger.debug("Bot object created")

async def _send_image(ctx: discord.ApplicationContext, header:bool):
    await ctx.defer(invisible=True)
    if header:
        with open(image_paths["header"], "rb") as image:
            file = discord.File(fp=image, filename="fw_header.png", description="Seal of the Office of the Flamewarden")
    else:
        with open(image_paths["footer"], "rb") as image:
            file = discord.File(fp=image, filename="fw_footer.png", description="Banner of the Office of the Flamewarden")
    await ctx.delete()
    await ctx.channel.send(file=file)

async def _send_vote_text(ctx: discord.ApplicationContext, name:str, author:discord.Member, type: str, link:str, quorum:int):
    await ctx.defer(invisible=True)
    if "the" in name.lower():
        the_name = name
    else:
        the_name = f"the {name}"
    if type == "constitutional":
        header = f"""## VOTING: {the_name.upper()}
        {the_name.title()} by <@{author.id}> is now at vote.

        **__Proposal__**:
        [LINK TO THE CONSTITUTIONAL AMENDMENT]({link})

        **__ Discussion__**:
        [LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})

        All Starborn are eligible to vote by selecting one of the following options in the poll:

        - **Aye** – In favor of the amendment

        - **Nay** – Opposed to the amendment

        - **Abstain** - Neither in favor nor opposed

        """
    elif type == "treaty":
        header = f"""## VOTING: {the_name.upper()} (TREATY)
        {the_name.title()} is now at vote.

        **__Proposal__**:
        [LINK TO THE TREATY]({link})

        **__ Discussion__**:
        [LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})

        All Starborn are eligible to vote by selecting one of the following options in the poll:

        - **Aye** – In favor of the signing of the treaty

        - **Nay** – Opposed to the signing of the treaty

        - **Abstain** - Neither in favor nor opposed

        """
    else:
        header = f"""## VOTING: {the_name.upper()}
        {the_name.title()} by <@{author.id}> is now at vote.

        **__Proposal__**:
        [LINK TO THE BILL]({link})

        **__ Discussion__**:
        [LINK TO THE DISCUSSION THREAD]({ctx.channel.jump_url})

        All Starborn are eligible to vote by selecting one of the following options in the poll:

        - **Aye** – In favor of the bill

        - **Nay** – Opposed to the bill

        - **Abstain** - Neither in favor nor opposed

        """
    footer = f"The voting period will last __72 hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a 60% majority of Aye votes to pass. Abstain votes are registered but not counted. The quorum for this vote is **{quorum}** (10% of Starborn)."
    text = header + footer
    await ctx.delete()
    await ctx.channel.send(content=text)

async def _create_vote_poll(ctx: discord.ApplicationContext, name: str, treaty: bool, duration: int):
    await ctx.defer(invisible=True)
    if "the" in name.lower():
        filler = " "
    else:
        filler = " the "
    if treaty:
        title = f'Shall the Halls of Solaris approve the signing of{filler}"{name}"?'
    else:
        title = f'Shall the Halls of Solaris pass{filler}"{name}"?'
    options = [
        discord.PollAnswer(text="Aye", emoji="✅"),
        discord.PollAnswer(text="Nay", emoji="❌"),
        discord.PollAnswer(text="Abstain", emoji="🔄")
    ]
    poll = discord.Poll(question=title, answers=options, duration=duration)
    await ctx.delete()
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
    embed = discord.Embed(title = "Flamebringer v1.2.0", description = f"For help or technical support message <@{error_ping}> on Discord.")
    logger.debug('Embed object created')

    await ctx.respond(embed = embed, ephemeral = True)
    logger.info('Info embed sent')

halls = bot.create_group("halls", "Commands relating to the Halls of Solaris")

@halls.command(name="vote", description="Create a poll for voting in the Halls of Solaris")
@discord.option("name",description="The name of the proposal going to vote",type=discord.SlashCommandOptionType.string)
@discord.option("treaty",description="Is the proposal a treaty?",type=discord.SlashCommandOptionType.boolean)
@discord.option("duration",description="Duration of the poll in hours (default: 48h)",type=discord.SlashCommandOptionType.integer,min_value=poll_durations["min"],max_value=poll_durations["max"],default=poll_durations["default"])
async def vote(ctx: discord.ApplicationContext, name: str, treaty: bool, duration: int):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _create_vote_poll(ctx=ctx, name=name, treaty=treaty, duration=duration)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

@halls.command(name="header", description="Post the seal of the Flamewarden")
async def header(ctx: discord.ApplicationContext):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _send_image(ctx=ctx, header=True)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

@halls.command(name="footer", description="Post the banner of the Flamewarden")
async def footer(ctx: discord.ApplicationContext):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _send_image(ctx=ctx, header=False)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

text = halls.create_subgroup("text", "Commands for posting vote text")

@text.command(name="constitutional", description="Post the vote text for a constitutional amendment")
@discord.option("name", description="The name of the proposal going to vote", type=discord.SlashCommandOptionType.string)
@discord.option("author", description="The Discord account of the author of the proposal", type=discord.SlashCommandOptionType.user)
@discord.option("link", description="The URL of the dispatch with the proposal text", type=discord.SlashCommandOptionType.string)
@discord.option("quorum", description="The quorum for the vote (10% of Starborn)", type=discord.SlashCommandOptionType.integer, min_value=7)
async def constitutional(ctx: discord.ApplicationContext, name:str, author:discord.Member, link:str, quorum:int):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _send_vote_text(ctx=ctx, name=name, author=author, type="constitutional", link=link, quorum=quorum)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

@text.command(name="treaty", description="Post the vote text for a treaty")
@discord.option("name", description="The name of the proposal going to vote", type=discord.SlashCommandOptionType.string)
@discord.option("link", description="The URL of the dispatch with the proposal text", type=discord.SlashCommandOptionType.string)
@discord.option("quorum", description="The quorum for the vote (10% of Starborn)", type=discord.SlashCommandOptionType.integer, min_value=7)
async def treaty(ctx: discord.ApplicationContext, name:str, link:str, quorum:int):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _send_vote_text(ctx=ctx, name=name, author='', type="constitutional", link=link, quorum=quorum)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

@text.command(name="standard", description="Post the vote text for a bill or amendment (non-constitutional)")
@discord.option("name", description="The name of the proposal going to vote", type=discord.SlashCommandOptionType.string)
@discord.option("author", description="The Discord account of the author of the proposal", type=discord.SlashCommandOptionType.user)
@discord.option("link", description="The URL of the dispatch with the proposal text", type=discord.SlashCommandOptionType.string)
@discord.option("quorum", description="The quorum for the vote (10% of Starborn)", type=discord.SlashCommandOptionType.integer, min_value=7)
async def standard(ctx: discord.ApplicationContext, name:str, author:discord.Member, link:str, quorum:int):
    permitted = False
    permitted_roles = [await ctx.guild.fetch_role(int(role)) for role in permitted_role_ids]
    for permitted_role in permitted_roles:
        if permitted_role in ctx.user.roles:
            permitted = True
            break
    if permitted:
        await _send_vote_text(ctx=ctx, name=name, author=author, type="standard", link=link, quorum=quorum)
    else:
        embed = discord.Embed(title = 'No Permissions', description = 'You do not have the required permissions to run this command.')
        logger.debug('Embed object created')

        await ctx.respond(embed = embed, ephemeral = True)
        logger.info('Error embed sent')

@bot.event
async def on_application_command_error(ctx:discord.ApplicationContext, error:discord.DiscordException):
    logger.error(error)
    await ctx.respond(f'<@{error_ping}> An unspecified error occurred.')

bot.run(token)
