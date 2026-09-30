# import required libraries
import logging  # log handler
import os # file handling
import sys # stream handling
import discord  # py-cord: discord bot framework
import validators # string validation
import datetime # datetime handling
import psycopg_pool # db
import psycopg.errors
import psycopg.types.enum
import asyncio
import cogs.private as private
from yaml import safe_load as load_yaml # yaml parsing

__version__ = "1.7.0b5"

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

# load DB connection params
connection_uri = f"postgresql://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@{os.getenv("POSTGRES_HOST")}:{os.getenv("POSTGRES_PORT")}/{os.getenv("POSTGRES_DB")}"

# create objects
class FlamebringerDB:
    def __init__(self, connection_uri: str, retry_on_fail = 3) -> None:
        "Initialize a basic asynchronous pool of connections to a PostgreSQL database"
        self.logger = logging.getLogger(__name__) # give this instance the module-level logger

        self.retry_on_fail = retry_on_fail

        self.connection_pool = psycopg_pool.AsyncConnectionPool(conninfo = connection_uri, min_size = 2, max_size = 16, open = False) # give this instance a connection pool to the DB
        self.logger.debug('Connection pool created')
    async def _open_connection_pool(self) -> None:
        await self.connection_pool.open() # opens the connection pool
        self.logger.debug('Connection pool opened')
        # register enums
        try:
            async with self.connection_pool.connection() as conn:
                self.logger.debug('Connection fetched from pool')
                psycopg.types.enum.register_enum(psycopg.types.enum.EnumInfo.fetch(conn, "PROPOSALTYPE"), conn, private.ProposalType)
                psycopg.types.enum.register_enum(psycopg.types.enum.EnumInfo.fetch(conn, "PROPOSALSTATE"), conn, private.ProposalState)
        except psycopg_pool.PoolTimeout as e:
            self.logger.warning(e)
            await self.connection_pool.check()
        except psycopg.errors.Error as e:
            self.logger.error(e)
    async def _close_connection_pool(self) -> None:
        await self.connection_pool.close() # closes the connection pool
        self.logger.debug('Connection pool closed')
    async def _query(self, query: str, params: tuple, autocommit = False) -> list | bool:
        "Send raw SQL queries to the database"
        try:
            async with self.connection_pool.connection() as conn: # get a connection from the pool
                await conn.set_autocommit(autocommit)
                self.logger.debug('Connection fetched from pool')
                async with conn.cursor() as cur: # open a cursor
                    self.logger.debug('Cursor opened')

                    await cur.execute(query, params)

                    self.logger.debug('Query executed successfully')

                    results = list(await cur.fetchall())

                    self.logger.debug('Results fetched successfully')

                    return results
        except psycopg_pool.PoolTimeout as e:
            self.logger.warning(e)
            await self.connection_pool.check()
            return False
        except psycopg.errors.Error as e:
            self.logger.error(e)
            return False
    async def add_proposal(self, name: str, authors: list[str], thread: int, type: private.ProposalType, state: private.ProposalState, id: str | None = None, results: list[int] | None = None) -> bool:
        return bool(await self._query(
            query = "INSERT INTO Halls (Name, Authors, Thread, Type, State, ID, Results) VALUES (%s, %s, %s, %s, %s, %s, %s);",
            params = (name, authors, thread, type, state, id, results)
        ))
    async def update_proposal_with_results_and_id(self, ref: int, id: str, results: list[int]) -> bool:
        return bool(await self._query(
            query = "UPDATE Halls SET ID = %s, Results = %s WHERE Ref = %s;",
            params = (id, results, ref)
        ))
    async def get_proposal_by_ref(self, ref: int) -> list:
        return await self._query(
            query = "SELECT 1 FROM Halls WHERE Ref = %s;",
            params = (ref)
        )
    async def get_proposal_by_id(self, id: str) -> list:
        return await self._query(
            query = "SELECT 1 FROM Halls WHERE ID = %s;",
            params = (id)
        )
    async def delete_proposal_by_ref(self, ref: int) -> bool:
        return bool(await self._query(
            query = "DELETE FROM Halls WHERE Ref = %s;",
            params = (ref)
        ))

class Flamebringer(discord.Bot):
    def __init__(self, connection_uri: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db = FlamebringerDB(connection_uri = connection_uri)

    async def on_ready() -> None:
        activity = discord.Game("Warding the Flame...")
        status = discord.Status.online
        await bot.change_presence(activity=activity, status=status)
        logger.info("Bot started, ready for interaction")

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

    async def on_thread_update(before: discord.Thread, after: discord.Thread): # ping the office when a new thread is created
        if after.parent == bot.get_channel(private.config[after.guild.id]["voting_forum_id"]): # in the correct channel
            if after.can_send():
                if not before.applied_tags == after.applied_tags: # if a change has actually been made
                    if after.parent.get_tag(private.config[after.guild.id]["debate_tag_id"]) in after.applied_tags and after.parent.get_tag(private.config[after.guild.id]["debate_tag_id"]) not in before.applied_tags:
                        embed = discord.Embed(title = "You have submitted your proposal into debate!", description = "You may motion your proposal to vote no sooner than 48 hours after the Flamewarden (or deputy) acknowledges the proposal.")
                        await after.send(content=f"<@&{"> <@&".join(map(str, private.config[after.guild.id]["fw_announcement_role_ids"]))}>", embed=embed)
                        logger.info("Debate ping sent")


intents = discord.Intents.default() # we need default intents so the bot actually functions well
intents.members = True # we also need members permission to calculate quorum, as that requires fetching the full member list of a role which needs the members intent
intents.messages = True # we need this to read our own messages, annoyingly
bot = Flamebringer(connection_uri = connection_uri, intents = intents)  # create a bot instance, with the previously set intents
logger.debug("Bot object created")

# load cogs
logger.info("Loading cogs...")
cogs = [
    "halls.py",
    "config.py"
]
for file in cogs: # for every file in the src directory
    logger.info(f"Loading {file}...")
    splitted = os.path.splitext(file)
    if splitted[1] == '.py': # if the file is python
        bot.load_extension(f"cogs.{splitted[0]}")

bot.run(token)
