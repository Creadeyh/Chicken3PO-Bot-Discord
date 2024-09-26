import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext
from interactions.ext.wait_for import *

import extensions.db_connection as db, extensions.checks as checks, extensions.utils as utils
from extensions.enums import ParticipationEnum, CoopStatusEnum, CoopGradeEnum

import uuid

GUILD_IDS = db.DatabaseConnection().get_all_guild_ids()

class Coop(interactions.Extension):

    def __init__(self, bot, pycord_bot, db_connection):
        self.bot: interactions.Client = bot
        self.pycord_bot: pycord_commands.Bot = pycord_bot
        self.db_connection: db.DatabaseConnection = db_connection

    #region Slash commands (contract channels)
    
    @interactions.extension_command(
        name="coop",
        description="Registers a new coop and displays it in the contract channel",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="coop_code",
                description="The code to join the coop",
                type=interactions.OptionType.STRING,
                required=True
            ),
            interactions.Option(
                name="grade",
                description="The grade of the coop (i.e. your grade as coop creator)",
                type=interactions.OptionType.STRING,
                required=True,
                choices=[
                    interactions.Choice(name=CoopGradeEnum.AAA.value, value=CoopGradeEnum.AAA.value),
                    interactions.Choice(name=CoopGradeEnum.AA.value, value=CoopGradeEnum.AA.value),
                    interactions.Choice(name=CoopGradeEnum.A.value, value=CoopGradeEnum.A.value),
                    interactions.Choice(name=CoopGradeEnum.B.value, value=CoopGradeEnum.B.value),
                    interactions.Choice(name=CoopGradeEnum.C.value, value=CoopGradeEnum.C.value)
                ]
            ),
            interactions.Option(
                name="locked",
                description="Whether or not the coop is locked at creation. Prevents people from joining",
                type=interactions.OptionType.BOOLEAN,
                required=False
            )
        ])
    async def add_coop(self, ctx: CommandContext, coop_code: str, grade: str, locked: bool=False):
        await ctx.defer(ephemeral=True)

        grade = CoopGradeEnum(grade)
        interac_guild = await ctx.get_guild()

        if not (contract_id := checks.check_contract_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))
        
        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # AFK permission
        if checks.check_is_afk(ctx_author, ctx_guild):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if "already_done" in contract_dic.keys() and ctx_author.id in contract_dic["already_done"]:
            await ctx.send("You have already completed this contract :smile:", ephemeral=True)
            return
        for coop in contract_dic["coops"]:
            if ctx_author.id in coop["members"]:
                await ctx.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                return

        coop_nb = len(contract_dic["coops"]) + 1
        data = await self.bot._http.get_channel(contract_dic["channel_id"])
        contract_channel = interactions.Channel(**data, _client=self.bot._http)
        contract_category = ctx_guild.get_channel(int(contract_channel.parent_id))

        # Creates coop channel and role
        coop_role = await ctx_guild.create_role(name=f"{contract_id}-{coop_nb}")
        coop_channel = await contract_category.create_text_channel(f"coop-{coop_nb}",
                                                                    overwrites={
                                                                        ctx_guild.default_role: pycord.PermissionOverwrite(view_channel=False),
                                                                        pycord.utils.get(ctx_guild.roles, name=self.pycord_bot.user.name): pycord.PermissionOverwrite(view_channel=True),
                                                                        pycord.utils.get(ctx_guild.roles, name="Coop Organizer"): pycord.PermissionOverwrite(view_channel=True),
                                                                        coop_role: pycord.PermissionOverwrite(view_channel=True),
                                                                    })
        to_pin = await coop_channel.send(":x: Do not share the coop code with anyone outside of this coop\n" +
                        ":x: Do not make the coop public unless told by a coop organizer\n\n" +
                        f"Coop grade: **{grade.value}**\n" +
                        f"Coop code: `{coop_code}`"
                        )
        await to_pin.pin()
        await ctx_author.add_roles(coop_role)

        # Gives coop creator role
        await ctx_author.add_roles(pycord.utils.get(ctx_guild.roles, name="Coop Creator"))

        # Updates running_coops
        self.db_connection.create_coop_record(
            int(interac_guild.id),
            contract_id,
            coop_code,
            ctx_author.id,
            coop_channel.id,
            locked,
            grade
        )
        self.db_connection.remove_member_remaining(int(interac_guild.id), contract_id, ctx_author.id)

        coop_content, join_button = await utils.generate_coop_message_content_component(self.pycord_bot, self.db_connection, ctx_guild, contract_id, coop_nb)
        coop_message = await contract_channel.send(content=coop_content, components=join_button)

        self.db_connection.set_coop_message_id(int(interac_guild.id), contract_id, coop_nb, int(coop_message.id))

        # Notif to coop organizers
        if self.db_connection.get_nb_remaining(int(interac_guild.id), contract_id) == 0:
            await utils.send_notif_no_remaining(self.db_connection, ctx_guild, contract_id)

        await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id)

        # Updates archive
        self.db_connection.set_member_participation(int(interac_guild.id), contract_id, contract_dic["date"], ctx_author.id, ParticipationEnum.YES)

        # Responds to the interaction
        await ctx.send("Coop registered :white_check_mark:", ephemeral=True)

    #endregion

    #region Slash commands (coop channels)

    @interactions.extension_command(
        name="lock",
        description="Locks a coop, preventing people from joining",
        scope=GUILD_IDS
    )
    async def lock_coop(self, ctx: CommandContext):

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_coop_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if contract_dic["coops"][coop_nb-1]["locked"]:
            await ctx.send(":warning: Coop is already locked", ephemeral=True)
            return

        self.db_connection.set_coop_lock_status(int(interac_guild.id), contract_id, coop_nb, True)

        await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id, coop_nb)
        
        # Responds to the interaction
        await ctx.send("Coop locked :white_check_mark:", ephemeral=True)
    
    @interactions.extension_command(
        name="unlock",
        description="Unlocks a coop, allowing people to join again",
        scope=GUILD_IDS
    )
    async def unlock_coop(self, ctx: CommandContext):

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_coop_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if not contract_dic["coops"][coop_nb-1]["locked"]:
            await ctx.send(":warning: Coop is already unlocked", ephemeral=True)
            return

        self.db_connection.set_coop_lock_status(int(interac_guild.id), contract_id, coop_nb, False)

        await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id, coop_nb)
        
        # Responds to the interaction
        await ctx.send("Coop unlocked :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="kick",
        description="Kicks someone from a coop",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="member",
                description="The member to be kicked from the coop",
                type=interactions.OptionType.USER,
                required=True
            )
        ])
    async def kick_from_coop(self, ctx: CommandContext, member: interactions.Member):

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_coop_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        # If user has left the guild, member is passed as user ID
        left = False
        if type(member) != interactions.Member:
            left = True
            member = await self.bot._http.get_user(member)
            member_id = int(member.user.id)
            ctx_send = ctx
        else:
            member = ctx_guild.get_member(int(member.id))
        
        alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")

        if left:
            pass
        # Check for alt
        elif alt_role in member.roles:
            action_row = interactions.ActionRow(components=[
                interactions.Button(
                    style=interactions.ButtonStyle.SECONDARY,
                    label=f"{self.db_connection.get_alt_main_name(int(interac_guild.id), member.id)}",
                    custom_id=f"main-{uuid.uuid4()}"
                ),
                interactions.Button(
                    style=interactions.ButtonStyle.SECONDARY,
                    label=f"{self.db_connection.get_alt_alt_name(int(interac_guild.id), member.id)}",
                    custom_id=f"alt-{uuid.uuid4()}"
                )
            ])
            await ctx.send("Which account do you want to kick ?", components=action_row, ephemeral=True)

            try:
                ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row, timeout=10)
            except asyncio.TimeoutError:
                await ctx.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                return
            if ctx_alt.custom_id.startswith("alt"):
                member_id = "alt" + str(member.id)
            else:
                member_id = member.id
            ctx_send = ctx_alt
        else:
            member_id = member.id
            ctx_send = ctx

        if (
            contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]
            and self.pycord_bot.owner_id != ctx_author.id
            and not ctx_author.guild_permissions.administrator
        ):
            await ctx_send.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if member_id not in contract_dic["coops"][coop_nb-1]["members"]:
            await ctx_send.send(":warning: Member is not in this coop", ephemeral=True)
            return
        if member_id == contract_dic["coops"][coop_nb-1]["creator"]:
            await ctx_send.send(":warning: You can't kick the coop creator", ephemeral=True)
            return

        # Updates running_coops
        self.db_connection.remove_member_coop(int(interac_guild.id), contract_id, coop_nb, member_id)
        self.db_connection.add_member_remaining(int(interac_guild.id), contract_id, member_id)

        await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id, coop_nb)
        await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id)

        # Removes coop role to remove access to coop channel
        # TODO keep role if alt/main is still in
        if str(member_id).startswith("alt"):
            discord_id = member_id.replace("alt", "")
        else:
            discord_id = member_id
        if not left:
            await member.remove_roles(pycord.utils.get(ctx_guild.roles, name=f"{contract_id}-{coop_nb}"))

        # Updates archive
        self.db_connection.set_member_participation(int(interac_guild.id), contract_id, contract_dic["date"], member_id, ParticipationEnum.NO)
        
        # Responds to the interaction
        await ctx_send.send(f"{member.mention} kicked from coop :white_check_mark:", ephemeral=True)
   
    @interactions.extension_command(
        name="coop-completed",
        description="Marks the coop as completed",
        scope=GUILD_IDS
    )
    async def coop_completed_slash(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_coop_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return
        
        await self.execute_coop_completed(ctx_guild, contract_id, contract_dic["channel_id"], coop_nb, contract_dic["coops"][coop_nb-1]["creator"])
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as completed :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="coop-failed",
        description="Marks the coop as failed. Returns members to the remaining list",
        scope=GUILD_IDS
    )
    async def coop_failed_slash(self, ctx: CommandContext):
        await ctx.defer(ephemeral=True)

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_coop_channel(self.db_connection, int(interac_guild.id), int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return
        
        await self.execute_coop_failed(ctx_guild, contract_id, contract_dic["channel_id"], contract_dic["date"], coop_nb, contract_dic["coops"][coop_nb-1])
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as failed :white_check_mark:", ephemeral=True)

    #endregion

    #region Context menus
    
    @interactions.extension_command(
        name="Coop completed",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    async def coop_completed_menu(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)

        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_context_menu_coop_message(self.db_connection, int(interac_guild.id), int(ctx.target.id))):
            await ctx.send(":warning: Not a coop message", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple
        
        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return

        await self.execute_coop_completed(ctx_guild, contract_id, contract_dic["channel_id"], coop_nb, contract_dic["coops"][coop_nb-1]["creator"])
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as completed :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="Coop failed",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    async def coop_failed_menu(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)
        
        interac_guild = await ctx.get_guild()

        if not (coop_infos_tuple := checks.check_context_menu_coop_message(self.db_connection, int(interac_guild.id), int(ctx.target.id))):
            await ctx.send(":warning: Not a coop message", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
        ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

        contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)

        # Owner, admin, coop organizer and coop creator permissions
        if not (
            await checks.check_is_owner(ctx)
            or checks.check_is_admin(ctx)
            or checks.check_is_coop_organizer(ctx_author, ctx_guild)
            or checks.check_is_coop_creator(ctx_author, self.db_connection, ctx_guild, contract_id, coop_nb)
        ):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if contract_dic["coops"][coop_nb-1]["completed_or_failed"] in [CoopStatusEnum.COMPLETED.value, CoopStatusEnum.FAILED.value]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return

        await self.execute_coop_failed(ctx_guild, contract_id, contract_dic["channel_id"], contract_dic["date"], coop_nb, contract_dic["coops"][coop_nb-1])

        # Responds to the interaction
        await ctx.send(f"Marked the coop as failed :white_check_mark:", ephemeral=True)

    #endregion

    #region Events

    @interactions.extension_listener(name="on_component")
    async def join_coop_event(self, ctx: ComponentContext):
        
        # Join coop button
        if ctx.data.custom_id.startswith("joincoop_"):
            await ctx.defer(ephemeral=True)

            contract_id = ctx.data.custom_id.split('_')[1]
            coop_nb = int(ctx.data.custom_id.split('_')[2])

            interac_guild = await ctx.get_guild()
            ctx_guild: pycord.Guild = self.pycord_bot.get_guild(int(interac_guild.id))
            ctx_author: pycord.Member = ctx_guild.get_member(int(ctx.author.user.id))

            author_id = ctx_author.id
            is_alt = False

            # Check for alt
            alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")
            if alt_role in ctx_author.roles:
                action_row = interactions.ActionRow(components=[
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{self.db_connection.get_alt_main_name(int(interac_guild.id), ctx_author.id)}",
                        custom_id=f"main-{uuid.uuid4()}"
                    ),
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{self.db_connection.get_alt_alt_name(int(interac_guild.id), ctx_author.id)}",
                        custom_id=f"alt-{uuid.uuid4()}"
                    )
                ])
                await ctx.send("Which account is joining ?", components=action_row, ephemeral=True)

                try:
                    ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row, timeout=10)
                except asyncio.TimeoutError:
                    await ctx.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                if ctx_alt.data.custom_id.startswith("alt"):
                    author_id = "alt" + str(ctx_author.id)
                    is_alt = True
                ctx_send = ctx_alt
            else:
                ctx_send = ctx

            # General checks
            contract_dic = self.db_connection.get_running_contract(int(interac_guild.id), contract_id)
            if "already_done" in contract_dic.keys() and author_id in contract_dic["already_done"]:
                await ctx_send.send("You have already completed this contract :smile:", ephemeral=True)
                return
            for coop in contract_dic["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                    return
            
            prev_remaining_count = len(contract_dic["remaining"])
            # If AFK and joins a coop, removes AFK role
            afk_role = pycord.utils.get(ctx_guild.roles, name="AFK")
            if not is_alt and afk_role in ctx_author.roles: # Alt doesn't count for AFK
                await ctx_author.remove_roles(afk_role)
            
            if author_id in contract_dic["remaining"]:
                self.db_connection.remove_member_remaining(int(interac_guild.id), contract_id, author_id)
            self.db_connection.add_member_coop(int(interac_guild.id), contract_id, coop_nb, author_id)

            # Notif to coop organizers, only if remaining wasn't already empty
            if self.db_connection.get_nb_remaining(int(interac_guild.id), contract_id) == 0 and prev_remaining_count > 0:
                await utils.send_notif_no_remaining(self.db_connection, ctx_guild, contract_id)

            # Updates archive
            self.db_connection.set_member_participation(int(interac_guild.id), contract_id, contract_dic["date"], author_id, ParticipationEnum.YES)

            # Gives coop role for access to coop channel
            await ctx_author.add_roles(pycord.utils.get(ctx_guild.roles, name=f"{contract_id}-{coop_nb}"))

            await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id, coop_nb)
            await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, ctx_guild, contract_id)

            # Sends coop code in hidden message
            await ctx_send.send(f"Code to join **Coop {coop_nb}** is: `{contract_dic['coops'][coop_nb-1]['code']}`\n" +
                                "Don't forget to activate your deflector and ship in bottle :wink:", ephemeral=True)
    
    #endregion

    #region Misc methods

    async def execute_coop_completed(self, guild: pycord.Guild, contract_id, contract_channel_id, coop_nb, coop_creator):

        # Deletes coop role and coop channel
        if not self.db_connection.get_guild_config_value(guild.id, "KEEP_COOP_CHANNELS"):
            await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()

            ctx_channel = await guild.fetch_channel(contract_channel_id)
            ctx_category = await guild.fetch_channel(ctx_channel.category_id)
            for channel in ctx_category.text_channels:
                if channel.name == f"coop-{coop_nb}":
                    await channel.delete()
                    break

        # Removes coop creator role
        creator = guild.get_member(coop_creator)
        # If creator has not left the guild
        if creator != None:
            # keep_role = False
            # for id, contract in self.db_connection.get_running_dic(guild.id).items():
            #     for i in range(len(contract["coops"])):
            #         if (
            #             contract["coops"][i]["creator"] == creator.id
            #             and id != contract_id
            #             and contract["coops"][i]["completed_or_failed"] == CoopStatusEnum.RUNNING.value
            #         ):
            #             keep_role = True
            # if not keep_role:
            if self.db_connection.get_nb_coops_created_by(guild.id, creator.id) < 2:
                await creator.remove_roles(pycord.utils.get(guild.roles, name="Coop Creator"))

        # Updates running_coops
        self.db_connection.set_coop_running_status(guild.id, contract_id, coop_nb, CoopStatusEnum.COMPLETED)

        await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, guild, contract_id, coop_nb)

    async def execute_coop_failed(self, guild: pycord.Guild, contract_id, contract_channel_id, contract_date, coop_nb, coop_dic):

        # Removes coop creator role
        creator = guild.get_member(coop_dic["creator"])
        # If creator has not left the guild
        if creator != None:
            # keep_role = False
            # for id, contract in self.db_connection.get_running_dic(guild.id).items():
            #     for i in range(len(contract["coops"])):
            #         if (
            #             contract["coops"][i]["creator"] == creator.id
            #             and id != contract_id
            #             and contract["coops"][i]["completed_or_failed"] == CoopStatusEnum.RUNNING.value
            #         ):
            #             keep_role = True
            # if not keep_role:
            if self.db_connection.get_nb_coops_created_by(guild.id, creator.id) < 2:
                await creator.remove_roles(pycord.utils.get(guild.roles, name="Coop Creator"))

        # Updates running_coops and archive
        self.db_connection.set_coop_running_status(guild.id, contract_id, coop_nb, CoopStatusEnum.FAILED)
        self.db_connection.unset_coop_creator(guild.id, contract_id, coop_nb)

        for member_id in coop_dic["members"]:
            self.db_connection.add_member_remaining(guild.id, contract_id, member_id)
            self.db_connection.remove_member_coop(guild.id, contract_id, coop_nb, member_id)
            self.db_connection.set_member_participation(guild.id, contract_id, contract_date, member_id, ParticipationEnum.NO)

        # Deletes coop role and coop channel
        if not self.db_connection.get_guild_config_value(guild.id, "KEEP_COOP_CHANNELS"):
            await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()

            ctx_channel = await guild.fetch_channel(contract_channel_id)
            ctx_category = await guild.fetch_channel(ctx_channel.category_id)
            for channel in ctx_category.text_channels:
                if channel.name == f"coop-{coop_nb}":
                    await channel.delete()
                    break

        await utils.update_coop_message(self.bot, self.pycord_bot, self.db_connection, guild, contract_id, coop_nb)
        await utils.update_contract_message(self.bot, self.pycord_bot, self.db_connection, guild, contract_id)

    #endregion

def setup(bot, pycord_bot, db_connection):
    Coop(bot, pycord_bot, db_connection)
