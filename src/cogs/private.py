# this file is in the cogs/ directory, but IS NOT A COG
# it provides various shared functions that act as the backend of bot commands

import discord
from yaml import safe_load as load_yaml # yaml parsing
from enum import Flag, nonmember, auto
from math import ceil # ceiling function
import datetime
import logging, os, sys

logger = logging.getLogger("flamebringer")  # get the logger for this script
handler = logging.StreamHandler(stream=sys.stdout)  # set logs to be sent to stdout
formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s") # format [time] - [module] - [error level] - [message]
handler.setFormatter(formatter) # attach the formatter to the handler
logger.addHandler(handler)  # attach the handler to the logger
logger.setLevel(logging.INFO)

# load config - this is now accessible at private.config
config_file = str(os.getenv("FLAMEBRINGER_CONFIG_FILE")) # get the config file path from the env var
if not os.path.isfile(config_file): # check the config file actually exists: if not,
    logger.error("FLAMEBRINGER_CONFIG_FILE environment variable is not a valid path, cannot start" ) # send an error message
    sys.exit() # quit
# if we get here, the config file must exist, so we
with open(config_file, "r") as file: # open the config file
    config = load_yaml(file) # parse it into a python object
config = config["config"] # navigate into the first section - everything should be under this first key so we don't need to constantly reference it
logger.info("Config loaded")
logger.setLevel(config["log_verbosity"]) # better hope that the config provided a valid number as we do no validation on this at all

# basic discord functions (calculate quorum, lock threads, set tags etc.)
async def _get_quorum(ctx: discord.ApplicationContext): # get quorum based on a pre-configured role
    quorum_role = ctx.guild.get_role(int(config[ctx.guild.id]["quorum_role_id"])) # fetch the role id from the config and get the Role object from the bot
    count = len([member for member in quorum_role.members if not(member.bot)]) # use a list comprehension to only count members who are not bots
    count_quorum = ceil(count / 10) # quorum is 10%, rounded up
    quorum = max(count_quorum, 7) # but if 10% is less than 7, we use 7
    return quorum

async def _set_tag(ctx: discord.ApplicationContext, tag:str): # set a tag on a thread, CLEARING ALL PREVIOUS TAGS
    if isinstance(ctx.channel, discord.threads.Thread): # check that the channel is actually a thread channel
        if isinstance(ctx.channel.parent, discord.ForumChannel): # check that the thread channel is in a forum channel, so it actually supports tags
            tag = ctx.channel.parent.get_tag(config[ctx.guild.id][f"{tag}_tag_id"]) # if those are both true, try to get the requested ForumTag object from the parent forum channel
            await ctx.channel.edit(applied_tags=[tag]) # apply that tag to the thread

async def _set_thread_lock(ctx: discord.ApplicationContext, lock = True): # lock or unlock a thread
    if isinstance(ctx.channel, discord.threads.Thread): # if it's a thread, it can be locked or unlocked
        await ctx.channel.edit(locked=lock) # so set the status requested

# basic python functions (string formatting etc.)
class ProposalType(Flag):
    legislative = auto()
    constitutional = auto()
    honorary = auto()
    holiday = auto()
    treaty = auto()
    legislatives = legislative | constitutional | holiday | treaty
    approvables = constitutional | honorary | treaty

    @property
    def is_legislative(self):
        return (self in ProposalType.legislatives)

    @property
    def voting_threshold(self):
        if self is ProposalType.constitutional:
            return (2/3)
        elif self is ProposalType.honorary:
            return (1/2)
        else:
            return (3/5)

    @property
    def is_approvable(self):
        return (self in ProposalType.approvables)

async def _format_definite_article(name: str): # format a name to have correct definite article (the)
    if "the" in name.lower() or name.split(' ')[0].lower() == 'repeal': # if 'the' is in the name
        the_name = name # the name should be "the [x]"
    else: # otherwise
        the_name = f"the {name}" # the name should be the "[x]"
    return the_name

async def _format_member_list(members: list[discord.Member]):
    if len(members) == 1: # if there is only one member in the list
        return f"<@{members[0].id}>" # just return their user ID formatted as a ping
    else:
        formatted_members = []
        for member in range(len(members)):
            if member == len(members) - 1: # if this is the final member
                formatted_members.append(f"and <@{members[member].id}>")
            else:
                formatted_members.append(f"<@{members[member].id}>")
        return ", ".join(formatted_members)

# command backend functions
# halls commands
async def _send_lock_message(ctx: discord.ApplicationContext):
    await ctx.channel.send(f"<@&{config[ctx.guild.id]['fw_primary_role_id']}> **The Office of the Flamewarden acknowledges the motion and second(s) and shall promptly schedule a vote.**")

async def _send_vote_status(ctx: discord.ApplicationContext):
    await ctx.channel.send("## __STATUS__: AT VOTE")

async def _send_image(ctx: discord.ApplicationContext, type: str):
    if type == 'header':
        with open(config["image_paths"]["header"], "rb") as image:
            file = discord.File(fp=image, filename="fw_header.png", description="Seal of the Office of the Flamewarden")
    else:
        with open(config["image_paths"]["footer"], "rb") as image:
            file = discord.File(fp=image, filename="fw_footer.png", description="Banner of the Office of the Flamewarden")
    await ctx.channel.send(file=file)

async def _send_tc_approval(ctx: discord.ApplicationContext, name: str, type: ProposalType, aye: int, nay: int, abstain: int):
    the_name = await _format_definite_article(name=name)

    if aye > nay:
        status = "approved"
        if type is ProposalType.treaty:
            fw_approval = f"**{the_name.title()} has passed the Halls of Solaris and has been approved by the Triune Circle. As of <t:{int(round(datetime.datetime.now().timestamp(),0))}:f> it is now formally ratified.**"
        elif type is ProposalType.constitutional:
            fw_approval = f"**{the_name.title()} has passed the Halls of Solaris and has been approved by the Triune Circle. As of <t:{int(round(datetime.datetime.now().timestamp(),0))}:f> it is now formally adopted into the Constitution.**"
        # ProposalType.honorary does not require fw_approval
        await _set_tag(ctx=ctx, tag="passed") # as these do not get passed until TC approval is given, we wait until this command
    else:
        status = "rejected"
        if treaty:
            fw_approval = f"**{the_name.title()} has been vetoed by the Triune Circle.**"
            await _set_tag(ctx=ctx, tag="failed")
        else:
            fw_approval = f"**{the_name.title()} has been vetoed by the Triune Circle. A petition to override the veto may now be submitted within 72 hours in this channel. The petition must receive the support of at least five Starborn, including the original proposer, to proceed.**"
            await _set_thread_lock(ctx=ctx, lock=False)
            await _set_tag(ctx=ctx, tag="vote") # if a motion can be made, its more voting than anything else

    if type is ProposalType.honorary:
        if abstain > 0:
            tc_approval = f"**The Triune Circle has approved the {the_name.title()} with {abstain} abstention, effective <t:{int(round(datetime.datetime.now().timestamp(),0))}:D>.**"
        else:
            tc_approval = f"**The Triune Circle has approved the {the_name.title()}, effective <t:{int(round(datetime.datetime.now().timestamp(),0))}:D>.**"
    else:
        if abstain > 0:
            tc_approval = f"**{the_name.title()}** has been **{status}** by the Triune Circle ({aye}-{nay})."
        else:
            tc_approval = f"**{the_name.title()}** has been **{status}** by the Triune Circle ({aye}-{nay}-{abstain})."

    for id in config[ctx.guild.id]["fw_announcement_role_ids"]:
        tc_approval = f"<@&{id}> " + tc_approval # append a ping of every role in fw_announcement_role_ids to the beginning of the tc_approval string

    await ctx.channel.send(content=tc_approval)

    if type is ProposalType.constitutional or type is ProposalType.treaty:
        await ctx.channel.send(content=fw_approval)

async def _send_vote_status(ctx: discord.ApplicationContext):
    await ctx.channel.send("## __STATUS__: AT VOTE")

async def _get_past_message_from_current_thread(ctx: discord.ApplicationContext, type: str) -> discord.Message | None:
    async for message in ctx.channel.history(limit = 4, oldest_first = False): # seeing how this is only linked to count, and that is only run directly after a vote, it is safest to limit to 4
        if message.author == ctx.guild.me: # if the message author is the same as the object representing the bot user in this guild
            if type == 'poll' and message.content == '' and message.poll is not None: # if we're looking for polls and we find a message with no text and a poll, authored by the bot
                return message
            elif type == 'status' and '## __STATUS__: ' in message.content: # if we're looking for status msesages and we find a message with the status heading authored by the bot
                return message
    return None

async def _edit_vote_status_with_count_and_sanction(ctx: discord.ApplicationContext, name:str, status_msg:discord.Message, poll_msg:discord.Message, type: ProposalType, quorum: int):
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
        if type == ProposalType.constitutional:
            if aye_percent > type.voting_threshold:
                passed = "APPROVED"
                sanction = f"**{the_name.title()} has passed the Halls of Solaris, meeting the required two-thirds majority.\nThe amendment is submitted to the <@&{config['tc_permission_role_id']}> who has now 72 hours to formally approve or veto it. Once approval is granted or if no action is taken within that timeframe, it will become law.**"
            else:
                passed = "REJECTED"
                sanction = f"**{the_name.title()} has failed to achieve the required two-thirds majority and therefore does not pass the Halls of Solaris.**"
        elif type == ProposalType.treaty:
            if aye_percent > type.voting_threshold:
                passed = "APPROVED"
                sanction = f"**{the_name.title()} has been approved by the Halls of Solaris. <@&{config['tc_permission_role_id']}>**"
            else:
                passed = "REJECTED"
                sanction = f"**{the_name.title()} has been rejected by the Halls of Solaris.**"
        else:
            if aye_percent > type.voting_threshold:
                passed = "PASSED"
                sanction = f"**{the_name.title()} has been passed by the Halls of Solaris and as of <t:{int(round(poll.expiry.timestamp(),0))}:f> it is in effect.**"
            else:
                passed = "FAILED"
                sanction = f"**{the_name.title()} has failed to achieve the required majority and therefore does not pass the Halls of Solaris.**"
    else:
        passed = f"FAILED TO REACH QUORUM\n*The quorum for this vote was {quorum}, but only {quorum_total} Starborn participated.*"
        sanction = f"**{the_name.title()} has failed to reach quorum and therefore does not pass the Halls of Solaris. The Flamewarden may reopen debate or extend the voting period.**"
    status = f"## __STATUS__: {passed}\n\n- Aye: {aye}\n- Nay: {nay}\n- Abstain: {abstain}\n\nTotal votes cast: {vote_total}\n\nAye = {round(aye_percent * 100, 1)}%"
    await status_msg.edit(content=status)
    await ctx.channel.send(content=sanction)
    if passed == "PASSED" and not type.is_approvable: # constitutional amendments  and treaties should only be marked as passed after TC approval. as they use 'APPROVED' as their status, this would serve on its own as a check against them, but extra steps are added to future proof against a change of the specific word used
        await _set_tag(ctx=ctx, tag="passed")
    elif passed == "FAILED" or passed == "REJECTED":
        await _set_tag(ctx=ctx, tag="failed")

async def _send_vote_text(ctx: discord.ApplicationContext, name: str, authors: list[discord.Member], type: ProposalType, link: str, duration: int):
    the_name = await _format_definite_article(name=name)
    quorum = await _get_quorum(ctx=ctx)
    if type is ProposalType.constitutional:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by {await _format_member_list(authors)} is now at vote.\n\n**__Proposal__**:\n[LINK TO THE CONSTITUTIONAL AMENDMENT]({link})\n\n**All** Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the amendment\n\n- **Nay** – Opposed to the amendment\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "66,6"
    elif type is ProposalType.treaty:
        header = f"## VOTING: {the_name.upper()} (TREATY)\n{the_name.title()} by {await _format_member_list(authors)} is now at vote.\n\n**__Proposal__**:\n[LINK TO THE TREATY]({link})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the signing of the treaty\n\n- **Nay** – Opposed to the signing of the treaty\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    else:
        header = f"## VOTING: {the_name.upper()}\n{the_name.title()} by {await _format_member_list(authors)} is now at vote.\n\n**__Proposal__**:\n[LINK TO THE BILL]({link})\n\nAll Starborn are eligible to vote by selecting one of the following options in the poll:\n\n- **Aye** – In favor of the bill\n\n- **Nay** – Opposed to the bill\n\n- **Abstain** - Neither in favor nor opposed\n"
        majority = "60"
    if type.is_legislative:
        footer = f"The voting period will last __{duration} hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a {majority}% majority of Aye votes to pass. Abstain votes are registered but not counted. The quorum for this vote is **{quorum}** (10% of Starborn)."
    else:
        footer = f"The voting period will last __{duration} hours__. If a Starborn loses their status during the voting period, they will no longer be eligible to vote, and their vote will be disregarded. Please note that the bill requires a {majority}% majority of Aye votes to pass. Abstain votes are registered but not counted. There is **no quorum** for this vote."
    text = header + footer
    await ctx.channel.send(content=text)

async def _create_vote_poll(ctx: discord.ApplicationContext, name: str, type: ProposalType, duration: int):
    the_name = await _format_definite_article(name=name)
    if type is ProposalType.treaty:
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