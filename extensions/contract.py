import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext
from interactions.ext.wait_for import *

import extensions.checks as checks, extensions.utils as utils

import json
from datetime import date
import uuid

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

    #region Slash commands (any channel)

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
    async def add_contract(self, ctx: CommandContext, contract_id: str, size: int, is_leggacy: bool):
    
        running_coops = utils.read_json("running_coops")
        archive = utils.read_json("participation_archive")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_channel = ctx_guild.get_channel(int(ctx.channel_id))
        ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.user.id))

        # Owner, admin and coop organizer permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

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
                                                    slowmode_delay=21600, # TODO change slowmode ?
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
        
        
        # Creates the contract in running_coops JSON
        contract_date = date.today().strftime("%Y-%m-%d")
        dic_contract = {
            "size": size,
            "date": contract_date,
            "is_leggacy": is_leggacy,
            "channel_id": channel.id,
            "message_id": None,
            "coops": [],
            "remaining": remaining_ids
        }
        if is_leggacy:
            dic_contract["already_done"] = already_done_ids
        
        running_coops[contract_id] = dic_contract
        utils.save_json("running_coops", running_coops)

        # Sends the contract message
        content, button = utils.generate_contract_message_content_component(self.pycord_bot, ctx_guild, contract_id)
        interac_channel = self.bot._http.get_channel(channel.id)
        interac_message = interac_channel.send(content=content, components=button)

        running_coops[contract_id]["message_id"] = int(interac_message.id)
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

    #endregion

    #region Slash commands (contract channels)

    @interactions.extension_command(
        name="contract-remove",
        description="If all coops are completed/failed, deletes the contract channel and category",
        scope=GUILD_IDS
    )
    async def remove_contract_slash(self, ctx: CommandContext):
        
        if not (contract_id := checks.check_contract_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return

        running_coops = utils.read_json("running_coops")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.user.id))

        # Owner, admin and coop organizer permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        for coop in running_coops[contract_id]["coops"]:
            if not coop["completed_or_failed"]:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        await self.execute_remove_contract(ctx_guild, contract_id)

        await ctx.send("Removed the contract :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="codes",
        description="Sends the codes of currently running coops",
        scope=GUILD_IDS
    )
    async def get_coop_codes(self, ctx: ComponentContext):

        if not (contract_id := checks.check_contract_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return
        
        running_coops = utils.read_json("running_coops")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.user.id))

        # Owner, admin and coop organizer permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return
        
        message = f"__**Coop codes for `{contract_id}`:**__\n"
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
    async def remove_contract_menu(self, ctx: ComponentContext):
        
        if not (contract_id := checks.check_context_menu_contract_message(int(ctx.target.id))):
            await ctx.send(":warning: Not a contract message", ephemeral=True)
            return

        running_coops = utils.read_json("running_coops")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.user.id))

        # Owner, admin and coop organizer permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return
        
        for coop in running_coops[contract_id]["coops"]:
            if not coop["completed_or_failed"]:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        
        await self.execute_remove_contract(ctx_guild, contract_id)

    #endregion

    #region Events

    @interactions.extension_listener("on_message_create")
    async def on_message_create(self, message: interactions.Message):
        # TODO Remove in interactions update after 4.1.0
        message._client = self.bot._http

        if not message.author.bot:
            running_coops = utils.read_json("running_coops")
            
            for contract in running_coops.values():
                if int(message.channel_id) == contract["channel_id"]:
                    await message.delete()

    @interactions.extension_listener("on_component")
    async def contract_already_done_event(self, ctx: ComponentContext):
        
        # Already done leggacy button
        if ctx.data.custom_id.startswith("leggacy_"):
            contract_id = ctx.data.custom_id.split('_')[1]

            interac_guild = await ctx.get_guild()
            ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
            ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.user.id))

            author_id = ctx_author.id

            # Check for alt
            alt_dic = utils.read_json("alt_index")
            alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")
            if alt_role in ctx_author.roles:
                action_row = interactions.ActionRow(
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{alt_dic[str(ctx_author.id)]['main']}",
                        custom_id=f"main-{uuid.uuid4()}"
                    ),
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{alt_dic[str(ctx_author.id)]['alt']}",
                        custom_id=f"alt-{uuid.uuid4()}"
                    )
                )
                await ctx.send("Which account has already done the contract ?", components=action_row, ephemeral=True)

                try:
                    ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row, timeout=10)
                except asyncio.TimeoutError:
                    await ctx.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                if ctx_alt.data.custom_id.startswith("alt"):
                    author_id = "alt" + str(ctx_author.id)
                ctx_send = ctx_alt
            else:
                ctx_send = ctx

            running_coops = utils.read_json("running_coops")
            for coop in running_coops[contract_id]["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                    return

            if author_id in running_coops[contract_id]["already_done"]:
                # Removes the player from already done
                
                archive = utils.read_json("participation_archive")
                for date, occurrence in archive[contract_id].items():
                    if (
                        date != running_coops[contract_id]["date"] and
                        str(author_id) in occurrence["participation"].keys() and
                        occurrence["participation"][str(author_id)] != "no"
                    ):
                        await ctx_send.send("I know from a trusted source you have done this contract :smile:", ephemeral=True)
                        return

                # Updates running_coops JSON
                running_coops[contract_id]["remaining"].append(author_id)
                running_coops[contract_id]["already_done"].remove(author_id)

                # Updates archive JSON
                archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(author_id)] = "no"

                # Saves JSONs
                utils.save_json("running_coops", running_coops)
                utils.save_json("participation_archive", archive)

                await utils.update_contract_message(self.bot, self.pycord_bot, ctx_guild, contract_id)

                # Responds to the interaction
                await ctx_send.send(f"Removed you from already done :white_check_mark:", ephemeral=True)

            else:
                # Adds the player to already done
            
                # Confirmation
                action_row = interactions.ActionRow(
                    interactions.Button(
                        style=interactions.ButtonStyle.SUCCESS,
                        label="Yes",
                        custom_id=f"yes-{uuid.uuid4()}"
                    ),
                    interactions.Button(
                        style=interactions.ButtonStyle.DANGER,
                        label="No",
                        custom_id=f"no-{uuid.uuid4()}"
                    )
                )
                await ctx_send.send("Are you sure you have already done this contract ?", components=action_row, ephemeral=True)
                try:
                    answer: ComponentContext = await wait_for_component(self.bot, components=action_row, timeout=10)
                except asyncio.TimeoutError:
                    await ctx_send.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                if answer.custom_id.startswith("no"):
                    await answer.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                else:
                    ctx_send = answer
            
                # Updates running_coops JSON
                if author_id in running_coops[contract_id]["remaining"]:
                    running_coops[contract_id]["remaining"].remove(author_id)
                running_coops[contract_id]["already_done"].append(author_id)

                # Notif to coop organizers
                if len(running_coops[contract_id]["remaining"]) == 0:
                    await utils.send_notif_no_remaining(ctx_guild, contract_id)

                # Updates archive JSON
                archive = utils.read_json("participation_archive")
                archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(author_id)] = "leggacy"

                # Saves JSONs
                utils.save_json("running_coops", running_coops)
                utils.save_json("participation_archive", archive)

                await utils.update_contract_message(self.bot, self.pycord_bot, ctx_guild, contract_id)

                # Responds to the interaction
                await ctx_send.send(f"Marked you as already done :white_check_mark:", ephemeral=True)

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
            if utils.is_member_active_in_any_running_coops(member.id):
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

def setup(bot, pycord_bot):
    Contract(bot, pycord_bot)
