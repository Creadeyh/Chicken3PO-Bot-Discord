import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext
from interactions.ext.wait_for import *

import extensions.utils as utils

import json
from datetime import date

with open("config.json", "r") as f:
    config = json.load(f)
    if config["guilds"]:
        GUILD_IDS = list(map(int, config["guilds"].keys()))
    else:
        GUILD_IDS = []

class Contract(interactions.Extension):

    def __init__(self, bot, pycord_bot):
        self.bot: interactions.Client = bot
        self.pycord_bot: pycord_commands.Bot = pycord_bot

    #region Check methods

    def check_context_menu_target_contract():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops.values():
                if ctx.target_message.id == contract["message_id"]:
                    return True
            return False
        return pycord_commands.check(predicate)

    #endregion

    #region Slash commands

    @interactions.extension_command(
        name="contract",
        description="Registers a new contract and creates a channel and category for it",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="contract_id",
                description="The unique ID for an EggInc contract",
                type=interactions.OptionType.STRING,
                required=True
            ),
            interactions.Option(
                name="size",
                description="Number of slots available in the contract",
                type=interactions.OptionType.INTEGER,
                required=True
            ),
            interactions.Option(
                name="is_leggacy",
                description="Whether the contract is leggacy or not",
                type=interactions.OptionType.BOOLEAN,
                required=True
            )
        ])
    # TODO Owner, admin and coop organizer permissions
    #@pycord_commands.check_any(pycord_commands.is_owner(), pycord_commands.has_permissions(administrator=True), pycord_commands.has_role("Coop Organizer"))
    async def add_contract(self, ctx: CommandContext, contract_id: str, size: int, is_leggacy: bool):
    
        running_coops = utils.read_json("running_coops")
        archive = utils.read_json("participation_archive")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_channel = await ctx_guild.get_channel(int(ctx.channel_id))


        if contract_id in running_coops.keys():
            await ctx.send(":warning: Contract already exists", ephemeral=True)
            return
        if not is_leggacy and contract_id in archive.keys():
            await ctx.send(":warning: Contract has to be a leggacy. Already registered in archive", ephemeral=True)
            return
        if size <= 1:
            await ctx.send(":warning: Invalid contract size", ephemeral=True)
            return
        
        # Creates a category and channel below commands channel for the contract, where coops will be listed
        category = await ctx_guild.create_category(contract_id)
        await category.move(after=ctx_channel.category)

        channel_overwrites = ctx_channel.overwrites.copy()
        for overwrite in channel_overwrites.values():
            overwrite.update(send_messages=False)
        if ctx_guild.default_role in channel_overwrites.keys():
            channel_overwrites[ctx_guild.default_role].update(view_channel=False)
        else:
            channel_overwrites[ctx_guild.default_role] = pycord.PermissionOverwrite(view_channel=False)
        
        for role_name in [self.pycord_bot.user.name, "Coop Organizer", "Coop Creator"]:
            role = pycord.utils.get(ctx_guild.roles, name=role_name)
            if role in channel_overwrites.keys():
                channel_overwrites[role].update(view_channel=True, send_messages=True)
            else:
                channel_overwrites[role] = pycord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await category.create_text_channel(contract_id,
                                                    topic="DO NOT TYPE HERE",
                                                    slowmode_delay=21600,
                                                    overwrites=channel_overwrites
                                                    )
        
        # Gets people without the AFK role and who haven't done the contract already (according to bot archive)
        def member_in_previous_coop(member_id):
            if contract_id not in archive.keys():
                return False
            for contract in archive[contract_id].values():
                if str(member_id) in contract["participation"].keys() and contract["participation"][str(member_id)] in ["yes", "leggacy"]:
                    return True
            return False
        
        guest_role = ctx_guild.get_role(utils.read_guild_config(ctx_guild.id, "GUEST_ROLE_ID"))
        afk_role = pycord.utils.get(ctx_guild.roles, name="AFK")
        alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")
        remaining_ids = []
        already_done_ids = []
        afk_ids = []
        for member in ctx_guild.members:
            if not member.bot and not (guest_role and guest_role in member.roles):
                if alt_role in member.roles:
                    ids = [member.id, "alt" + str(member.id)]
                else:
                    ids = [member.id]
                for id in ids:
                    if is_leggacy and member_in_previous_coop(id):
                        already_done_ids.append(id)
                    elif afk_role in member.roles:
                        afk_ids.append(id)
                    else:
                        remaining_ids.append(id)
        
        # Sends the contract message
        contract_string = ("==============================\n"
                        + f"**{'LEGGACY ' if is_leggacy else ''}Contract available**\n"
                        + f"*Contract ID:* `{contract_id}`\n"
                        + f"*Coop size:* {size}\n"
                        + "==============================\n\n"
                        + (
                            (
                                f"**Already done:**\n{''.join([await utils.get_member_mention(id, ctx_guild, self.pycord_bot) for id in already_done_ids])}"
                                + ("\n" if already_done_ids else "")
                                + "\n"
                            )
                            if is_leggacy else ""
                        )
                        + f"**Remaining: ({len(remaining_ids)})**\n{''.join([await utils.get_member_mention(id, ctx_guild, self.pycord_bot) for id in remaining_ids])}\n"
                        )
        if is_leggacy:
            component = interactions.Button(
                style=interactions.ButtonStyle.PRIMARY,
                label="I've already done this contract",
                custom_id=f"leggacy_{contract_id}"
            )
        else:
            component = None
        message = await channel.send(contract_string, components=component)
        
        # Creates the contract in running_coops JSON
        contract_date = date.today().strftime("%Y-%m-%d")
        dic_contract = {
            "size": size,
            "date": contract_date,
            "is_leggacy": is_leggacy,
            "channel_id": channel.id,
            "message_id": message.id,
            "coops": [],
            "remaining": remaining_ids
        }
        if is_leggacy:
            dic_contract["already_done"] = already_done_ids
        
        running_coops[contract_id] = dic_contract
        utils.save_json("running_coops", running_coops)

        # Creates the contract in archive JSON
        if not contract_id in archive.keys():
            archive[contract_id] = {}
        
        participation = {}
        for id in remaining_ids:
            participation[str(id)] = "no"
        for id in already_done_ids:
            participation[str(id)] = "leggacy"
        for id in afk_ids:
            participation[str(id)] = "afk"
        
        archive[contract_id][contract_date] = {
            "is_leggacy": is_leggacy,
            "participation": participation
        }
        utils.save_json("participation_archive", archive)

        # Responds to the interaction
        await ctx.send("Contract registered :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="contract-remove",
        description="If all coops are completed/failed, deletes the contract channel and category",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="contract_id",
                description="The unique ID for an EggInc contract",
                type=interactions.OptionType.STRING,
                required=True
            )
        ])
    # TODO Owner, admin and coop organizer permissions
    async def remove_contract_slash(self, ctx: CommandContext, contract_id: str):

        running_coops = utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", ephemeral=True)
            return

        for coop in running_coops[contract_id]["coops"]:
            if not coop["completed_or_failed"]:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        
        await self.execute_remove_contract(ctx_guild, contract_id)

        await ctx.send("Removed the contract :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="codes",
        description="Sends the codes of currently running coops",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="contract_id",
                description="The contract for which you want the coop codes. If not given, sends for all running contracts",
                type=interactions.OptionType.STRING,
                required=False
            )
        ])
    # TODO Owner, admin and coop organizer permissions
    async def get_coop_codes(self, ctx: ComponentContext, contract_id: str=""):

        running_coops = utils.read_json("running_coops")

        if contract_id:
            if contract_id not in running_coops.keys():
                await ctx.send(":warning: Contract does not exist or is not currently running", ephemeral=True)
                return
            contract_ids = [contract_id]
        else:
            contract_ids = running_coops.keys()
        
        message = "__**Coop codes:**__\n"
        for id in contract_ids:
            message = message + "\n" + f"**Contract `{id}`:**\n"
            for i in range(len(running_coops[id]["coops"])):
                message = message + f"- Coop {i+1}: `{running_coops[id]['coops'][i]['code']}`\n"

        await ctx.send(message, ephemeral=True)

    #endregion

    #region Context menus

    @interactions.extension_command(
        name="Remove contract",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    # TODO @check_context_menu_target_contract()
    # TODO Owner, admin and coop organizer permissions
    async def remove_contract_menu(self, ctx: ComponentContext):
        
        running_coops = utils.read_json("running_coops")

        for id in running_coops:
            if int(ctx.target.id) == running_coops[id]["message_id"]:
                contract_id = id
        
        for coop in running_coops[contract_id]["coops"]:
            if not coop["completed_or_failed"]:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        
        await self.execute_remove_contract(ctx_guild, contract_id)

    #endregion

    #region Misc methods

    async def execute_remove_contract(self, guild: pycord.Guild, contract_id):

        running_coops = utils.read_json("running_coops")

        # Deletes contract channel, category, and all coop channels and roles leftover
        contract_channel = pycord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"])

        for channel in contract_channel.category.channels:
            if channel != contract_channel:
                coop_nb = channel.name.split("-")[1]
                await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()
                await channel.delete()

        await contract_channel.category.delete()
        await contract_channel.delete()

        # Updates running_coops JSON
        running_coops.pop(contract_id)

        # Checks for new AFK
        archive = utils.read_json("participation_archive")
        date_dic = {}
        for id, occurrences in archive.items():
            for date, occurrence in occurrences.items():
                # If the contract occurrence is still running, ignore
                if id in running_coops.keys() and date == running_coops[id]["date"]:
                    continue
                # Else
                if date not in date_dic.keys():
                    date_dic[date] = []
                date_dic[date].append(occurrence)
        # Sorts by date
        date_dic = dict(sorted(date_dic.items(), reverse=True))
        # If members has not participated in last number of archived coops defined in COOPS_BEFORE_AFK (excluding already done leggacies),
        # and has not joined one of the running coops, gives him AFK role
        # Alt accounts are not taken into account
        for member in guild.members:
            if utils.is_member_active_in_running_coops(member.id):
                continue
            count = 0
            no_count = 0
            i = 0
            while count < utils.read_guild_config(guild.id, "COOPS_BEFORE_AFK") and i < len(date_dic):
                key = list(date_dic.keys())[i]
                for coop in date_dic[key]:
                    if str(member.id) not in coop["participation"].keys():
                        continue
                    if coop["participation"][str(member.id)] in ["no", "afk"]:
                        no_count = no_count + 1
                    if coop["participation"][str(member.id)] != "leggacy":
                        count = count + 1
                i = i + 1
            if no_count >= utils.read_guild_config(guild.id, "COOPS_BEFORE_AFK"):
                await member.add_roles(pycord.utils.get(guild.roles, name="AFK"))
        
        # Saves running_coops JSON
        utils.save_json("running_coops", running_coops)

    #endregion

    @interactions.extension_command(
        name="test",
        description="Help command",
        scope=GUILD_IDS
    )
    async def test(self, ctx: CommandContext):
        button = interactions.Button(
                style=interactions.ButtonStyle.PRIMARY,
                label="test button",
                custom_id="test_custom_id"
            )
        await ctx.send("test message", components=button)

def setup(bot, pycord_bot):
    Contract(bot, pycord_bot)
