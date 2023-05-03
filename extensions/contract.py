import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext
from interactions.ext.wait_for import *

import extensions.db_connection as db, extensions.checks as checks, extensions.utils as utils
from extensions.enums import CoopStatusEnum, ParticipationEnum

from datetime import date
import uuid

GUILD_IDS = utils.load_db_connection().get_all_guild_ids()

class Contract(interactions.Extension):

    def __init__(self, bot, pycord_bot, db_connection):
        self.bot: interactions.Client = bot
        self.pycord_bot: pycord_commands.Bot = pycord_bot
        self.db_connection: db.DatabaseConnection = db_connection

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
    async def add_contract(self, ctx: CommandContext, contract_id: str, size: int, is_leggacy: bool=False):
        await ctx.defer(ephemeral=True)

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_channel = ctx_guild.get_channel(int(ctx.channel_id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        # Owner, admin and coop organizer permissions
        if not (await checks.check_is_owner(ctx) or checks.check_is_admin(ctx) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if self.db_connection.is_contract_running(int(interac_guild.id), contract_id):
            await ctx.send(":warning: Contract already exists", ephemeral=True)
            return
        if not is_leggacy and self.db_connection.is_contract_in_archive(int(interac_guild.id), contract_id):
            await ctx.send(":warning: Contract has to be a leggacy. Already registered in archive", ephemeral=True)
            return
        if size <= 1:
            await ctx.send(":warning: Invalid contract size", ephemeral=True)
            return
        
        # Creates a category and channel below commands channel for the contract, where coops will be listed
        category = await ctx_guild.create_category(contract_id)
        await category.move(after=ctx_channel.category)

        channel_overwrites = ctx_channel.overwrites.copy()
        if ctx_guild.default_role in channel_overwrites.keys():
            channel_overwrites[ctx_guild.default_role].update(view_channel=False)
        else:
            channel_overwrites[ctx_guild.default_role] = pycord.PermissionOverwrite(view_channel=False)
        
        for role_name in [self.pycord_bot.user.name, "Coop Organizer", "Coop Creator"]:
            role = pycord.utils.get(ctx_guild.roles, name=role_name)
            if role in channel_overwrites.keys():
                channel_overwrites[role].update(view_channel=True)
            else:
                channel_overwrites[role] = pycord.PermissionOverwrite(view_channel=True)

        channel = await category.create_text_channel(contract_id, slowmode_delay=21600, overwrites=channel_overwrites)
        data = await self.bot._http.get_channel(channel.id)
        interac_channel = interactions.Channel(**data, _client=self.bot._http)
        
        # Gets people without the AFK role and who haven't done the contract already (according to bot archive)
        guest_role = ctx_guild.get_role(self.db_connection.get_guild_config_value(ctx_guild.id, "GUEST_ROLE_ID"))
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
                    if is_leggacy and self.db_connection.has_member_participated_in_previous_contract(int(interac_guild.id), contract_id, id):
                        already_done_ids.append(id)
                    elif afk_role in member.roles:
                        afk_ids.append(id)
                    else:
                        remaining_ids.append(id)

        # Creates the contract in DB (running and archive)
        contract_date = date.today().strftime("%Y-%m-%d")
        self.db_connection.create_contract_record(
            int(interac_guild.id),
            contract_id,
            size,
            contract_date,
            is_leggacy,
            int(interac_channel.id),
            remaining_ids,
            None,
            already_done_ids,
            afk_ids
        )

        # Sends the contract message
        content, button = await utils.generate_contract_message_content_component(self.pycord_bot, self.db_connection, ctx_guild, contract_id)
        interac_message = await interac_channel.send(content=content, components=button)

        self.db_connection.set_contract_message_id(int(interac_guild.id), contract_id, int(interac_message.id))

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
        await ctx.defer(ephemeral=True)

        interac_guild = await ctx.get_guild()

        if not (contract_id := checks.check_contract_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin and coop organizer permissions
        if not (await checks.check_is_owner(ctx) or checks.check_is_admin(ctx) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        for coop in contract_dic["coops"]:
            if coop["completed_or_failed"] == CoopStatusEnum.RUNNING.value:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        await self.execute_remove_contract(ctx_guild, contract_id, contract_dic["channel_id"])

        await ctx.send("Removed the contract :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="codes",
        description="Sends the codes of currently running coops",
        scope=GUILD_IDS
    )
    async def get_coop_codes(self, ctx: ComponentContext):

        interac_guild = await ctx.get_guild()

        if not (contract_id := checks.check_contract_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return
        
        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin and coop organizer permissions
        if not (await checks.check_is_owner(ctx) or checks.check_is_admin(ctx) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return
        
        message = f"__**Coop codes for `{contract_id}`:**__\n"
        for i in range(len(contract_dic["coops"])):
            message = message + f"- Coop {i+1}: `{contract_dic['coops'][i]['code']}`\n"

        await ctx.send(message, ephemeral=True)

    #endregion

    #region Context menus

    @interactions.extension_command(
        name="Remove contract",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    async def remove_contract_menu(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)
        
        interac_guild = await ctx.get_guild()

        if not (contract_id := checks.check_context_menu_contract_message(self.db_connection, int(interac_guild.id), int(ctx.target.id))):
            await ctx.send(":warning: Not a contract message", ephemeral=True)
            return

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin and coop organizer permissions
        if not (await checks.check_is_owner(ctx) or checks.check_is_admin(ctx) or checks.check_is_coop_organizer(ctx_author, ctx_guild)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return
        
        for coop in contract_dic["coops"]:
            if coop["completed_or_failed"] == CoopStatusEnum.RUNNING.value:
                await ctx.send(":warning: Some coops are still running", ephemeral=True)
                return
        
        await self.execute_remove_contract(ctx_guild, contract_id, contract_dic["channel_id"])

    #endregion

    #region Events

    @interactions.extension_listener(name="on_message_create")
    async def on_message_create(self, message: interactions.Message):
        if not message.author.bot and int(message.channel_id) in self.db_connection.get_all_contract_channel_ids(int(message.guild_id)):
            await message.delete()

    @interactions.extension_listener(name="on_component")
    async def contract_already_done_event(self, ctx: ComponentContext):
        
        # Already done leggacy button
        if ctx.data.custom_id.startswith("leggacy_"):
            contract_id = ctx.data.custom_id.split('_')[1]

            interac_guild = await ctx.get_guild()
            ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
            ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

            author_id = ctx_author.id
            
            # Check for alt
            alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")
            if alt_role in ctx_author.roles:
                action_row = interactions.ActionRow(components=[
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=self.db_connection.get_alt_main_name(int(interac_guild.id), ctx_author.id),
                        custom_id=f"main-{uuid.uuid4()}"
                    ),
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=self.db_connection.get_alt_alt_name(int(interac_guild.id), ctx_author.id),
                        custom_id=f"alt-{uuid.uuid4()}"
                    )
                ])
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

            contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)
            for coop in contract_dic["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                    return

            if author_id in contract_dic["already_done"]:
                # Removes the player from already done

                # Updates DB
                self.db_connection.add_member_remaining(int(interac_guild.id), contract_id, author_id)
                self.db_connection.remove_member_already_done(int(interac_guild.id), contract_id, author_id)
                self.db_connection.set_member_participation(int(interac_guild.id), contract_id, contract_dic["date"], author_id, ParticipationEnum.NO)

                await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id)

                # Responds to the interaction
                await ctx_send.send(f"Removed you from already done :white_check_mark:", ephemeral=True)

            else:
                # Adds the player to already done
            
                # Confirmation
                action_row = interactions.ActionRow(components=[
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
                ])
                await ctx_send.send("Are you sure you have already done this contract ?", components=action_row, ephemeral=True)
                try:
                    answer: ComponentContext = await self.bot.wait_for_component(components=action_row, timeout=10)
                except asyncio.TimeoutError:
                    await ctx_send.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                if answer.custom_id.startswith("no"):
                    await answer.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                else:
                    ctx_send = answer
            
                # Updates running_coops
                if author_id in contract_dic["remaining"]:
                    self.db_connection.remove_member_remaining(int(interac_guild.id), contract_id, author_id)
                self.db_connection.add_member_already_done(int(interac_guild.id), contract_id, author_id)

                # Notif to coop organizers
                if self.db_connection.get_nb_remaining(int(interac_guild.id), contract_id) == 0:
                    await utils.send_notif_no_remaining(self.db_connection, ctx_guild, contract_id)

                # Updates archive
                self.db_connection.set_member_participation(int(interac_guild.id), contract_id, contract_dic["date"], author_id, ParticipationEnum.LEGGACY)

                await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id)

                # Responds to the interaction
                await ctx_send.send(f"Marked you as already done :white_check_mark:", ephemeral=True)

    #endregion

    #region Misc methods

    async def execute_remove_contract(self, guild: pycord.Guild, contract_id: str, contract_channel_id: int):

        # Deletes contract channel, category, and all coop channels and roles leftover
        contract_channel = await guild.fetch_channel(contract_channel_id)
        contract_category = await guild.fetch_channel(contract_channel.category_id)

        for channel in contract_category.channels:
            if channel != contract_channel:
                coop_nb = channel.name.split("-")[1]
                await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()
                await channel.delete()

        await contract_category.delete()
        await contract_channel.delete()

        # DB update
        self.db_connection.remove_running_contract(guild.id, contract_id)

        # Checks for new AFK
        
        date_dic = self.db_connection.get_archive_by_date(guild.id)
        # If members has not participated in last number of archived coops defined in COOPS_BEFORE_AFK (excluding already done leggacies),
        # and has not joined one of the running coops, gives him AFK role
        # Alt accounts are not taken into account
        for member in guild.members:
            if utils.is_member_active_in_any_running_coops(member.id, self.db_connection, guild.id):
                continue
            count = 0
            no_count = 0
            i = 0
            while count < self.db_connection.get_guild_config_value(guild.id, "COOPS_BEFORE_AFK") and i < len(date_dic):
                key = list(date_dic.keys())[i]
                for coop in date_dic[key]:
                    if str(member.id) not in coop["participation"].keys():
                        continue
                    if coop["participation"][str(member.id)] in [ParticipationEnum.NO.value, ParticipationEnum.AFK.value]:
                        no_count = no_count + 1
                    if coop["participation"][str(member.id)] != ParticipationEnum.LEGGACY.value:
                        count = count + 1
                i = i + 1
            if no_count >= self.db_connection.get_guild_config_value(guild.id, "COOPS_BEFORE_AFK"):
                await member.add_roles(pycord.utils.get(guild.roles, name="AFK"))

    #endregion

def setup(bot, pycord_bot, db_connection):
    Contract(bot, pycord_bot, db_connection)
