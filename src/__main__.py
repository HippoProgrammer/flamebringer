# import required libraries
import logging  # log handler
import os # file handling
import sys # stream handling
import discord  # py-cord: discord bot framework
import validators # string validation
import datetime # datetime handling
import cogs.private as private
from yaml import safe_load as load_yaml # yaml parsing

__version__ = "1.7.0b3"

# configure logging
logger = logging.getLogger("flamebringer")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s") # format [time] - [module] - [error level] - [message]
handler.setFormatter(formatter) # attach the formatter to the handler
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(private.config["log_verbosity"]) # better hope that the config provided a valid number as we do no validation on this at all
logger.info("Logging started")

# load token
token_file = private.config["token_file"] # get the token file path from the config file
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
intents.messages = True # we need this to read our own messages, annoyingly
bot = discord.Bot(intents = intents)  # create a bot instance, with the previously set intents
logger.debug("Bot object created")

# load cogs
logger.info("Loading cogs...")
cogs = [
    "automatic.py",
    "manual.py",
    "config.py"
]
for file in cogs: # for every file in the src directory
    logger.info(f"Loading {file}...")
    splitted = os.path.splitext(file)
    if splitted[1] == '.py': # if the file is python
        bot.load_extension(f"cogs.{splitted[0]}")

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
        await ctx.channel.send(f'<@{private.config[ctx.guild.id]["error_ping"]}> An unspecified error occurred.')

@bot.event
async def on_thread_create(thread: discord.Thread): # ping the office when a new thread is created
    if thread.parent == bot.get_channel(private.config[thread.guild.id]["voting_forum_id"]): # in the correct channel
        if thread.can_send():
            if thread.parent.get_tag(private.config[thread.guild.id]["debate_tag_id"]) in thread.applied_tags:
                embed = discord.Embed(title = "You have submitted your proposal into debate!", description = "You may motion your proposal to vote no sooner than 48 hours after the Flamewarden (or deputy) acknowledges the proposal.")
                await thread.send(content=f"<@&{"> <@&".join(map(str, private.config[thread.guild.id]["fw_announcement_role_ids"]))}>", embed=embed)
                logger.info("Debate ping sent")
            else:
                embed = discord.Embed(title = "You have submitted your proposal!", description = "You may motion your proposal to debate at any time by modifying this thread's tags to 'In Debate'.")
                await thread.send(embed=embed)
                logger.info("Submission embed sent")

@bot.event
async def on_thread_update(before: discord.Thread, after: discord.Thread): # ping the office when a new thread is created
    if after.parent == bot.get_channel(private.config[after.guild.id]["voting_forum_id"]): # in the correct channel
        if after.can_send():
            if not before.applied_tags == after.applied_tags: # if a change has actually been made
                if after.parent.get_tag(private.config[after.guild.id]["debate_tag_id"]) in after.applied_tags and after.parent.get_tag(private.config[after.guild.id]["debate_tag_id"]) not in before.applied_tags:
                    embed = discord.Embed(title = "You have submitted your proposal into debate!", description = "You may motion your proposal to vote no sooner than 48 hours after the Flamewarden (or deputy) acknowledges the proposal.")
                    await after.send(content=f"<@&{"> <@&".join(map(str, private.config[after.guild.id]["fw_announcement_role_ids"]))}>", embed=embed)
                    logger.info("Debate ping sent")

bot.run(token)
