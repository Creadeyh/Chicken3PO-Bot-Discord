import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext
from interactions.ext.wait_for import *

from extensions import checks, utils

import json
from datetime import date
import uuid

with open("config.json", "r") as f:
    config = json.load(f)
    if config["guilds"]:
        GUILD_IDS = list(map(int, config["guilds"].keys()))
    else:
        GUILD_IDS = []

class Coop(interactions.Extension):

    def __init__(self, bot, pycord_bot):
        self.bot: interactions.Client = bot
        self.pycord_bot: pycord_commands.Bot = pycord_bot


    #region Check methods

    # def is_not_afk():
    #     def predicate(ctx):
    #         afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
    #         return afk_role not in ctx.author.roles
    #     return commands.check(predicate)
    
    # def is_coop_creator_context_menu():
    #     def predicate(ctx):
    #         running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
    #         for contract in running_coops.values():
    #             for coop in contract["coops"]:
    #                 if ctx.target_message.id == coop["message_id"] and ctx.author.id == coop["creator"]:
    #                     return True
    #         return False
    #     return commands.check(predicate)

    #endregion

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
                name="locked",
                description="Whether or not the coop is locked at creation. Prevents people from joining",
                type=interactions.OptionType.BOOLEAN,
                required=False
            )
        ])
    # TODO @is_not_afk()
    async def add_coop(self, ctx: CommandContext, coop_code: str, locked: bool=False):
        
        if not (contract_id := checks.check_contract_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a contract channel", ephemeral=True)
            return

        running_coops = utils.read_json("running_coops")
        if "already_done" in running_coops[contract_id].keys() and ctx.author.id in running_coops[contract_id]["already_done"]:
            await ctx.send("You have already completed this contract :smile:", ephemeral=True)
            return
        for coop in running_coops[contract_id]["coops"]:
            if ctx.author.id in coop["members"]:
                await ctx.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))

        # Creates coop message with join button
        coop_nb = len(running_coops[contract_id]["coops"]) + 1
        contract_channel = pycord.utils.get(ctx_guild.channels, id=running_coops[contract_id]["channel_id"])
        join_button = interactions.Button(
            style=(interactions.ButtonStyle.DANGER if locked else interactions.ButtonStyle.SUCCESS),
            label=f"{'LOCKED' if locked else 'Join'}",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=locked
        )
        
        if utils.read_guild_config(ctx_guild.id, "USE_EMBEDS"):
            coop_embed = utils.get_coop_embed(coop_nb, running_coops[contract_id]['size'], ctx_author.mention)
            coop_message = await contract_channel.send(embed=coop_embed, components=join_button)
        else:
            coop_content = utils.get_coop_content(coop_nb, running_coops[contract_id]['size'], ctx_author.mention)
            coop_message = await contract_channel.send(content=coop_content, components=join_button)

        # Creates coop channel and role
        coop_role = await ctx_guild.create_role(name=f"{contract_id}-{coop_nb}")
        coop_channel = await contract_channel.category.create_text_channel(f"coop-{coop_nb}",
                                                                    overwrites={
                                                                        ctx_guild.default_role: pycord.PermissionOverwrite(view_channel=False),
                                                                        pycord.utils.get(ctx_guild.roles, name=self.pycord_bot.user.name): pycord.PermissionOverwrite(view_channel=True),
                                                                        pycord.utils.get(ctx_guild.roles, name="Coop Organizer"): pycord.PermissionOverwrite(view_channel=True),
                                                                        coop_role: pycord.PermissionOverwrite(view_channel=True),
                                                                    })
        to_pin = await coop_channel.send(":x: Do not share the coop code with anyone outside of this coop\n" +
                        ":x: Do not make the coop public unless told by a coop organizer\n\n" +
                        f"Coop code: `{coop_code}`"
                        )
        await to_pin.pin()
        await ctx_author.add_roles(coop_role)

        # Gives coop creator role
        await ctx_author.add_roles(pycord.utils.get(ctx_guild.roles, name="Coop Creator"))

        # Updates running_coops JSON
        coop_dic = {
            "code": coop_code,
            "creator": ctx_author.id,
            "channel_id": coop_channel.id,
            "message_id": coop_message.id,
            "locked": locked,
            "completed_or_failed": False,
            "members": [ctx_author.id]
        }
        running_coops[contract_id]["coops"].append(coop_dic)
        running_coops[contract_id]["remaining"].remove(ctx_author.id)

        # Notif to coop organizers
        if len(running_coops[contract_id]["remaining"]) == 0:
            await self.send_notif_no_remaining(ctx.guild, contract_id)

        # Updates contract message
        remaining_mentions = []
        for id in running_coops[contract_id]["remaining"]:
            remaining_mentions.append(await utils.get_member_mention(id, ctx_guild, self.pycord_bot))
        
        contract_message = await contract_channel.fetch_message(running_coops[contract_id]["message_id"])
        remaining_index = contract_message.content.index("**Remaining:")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})**\n{''.join(remaining_mentions)}\n"
        await contract_message.edit(content=new_contract_content)

        # Saves JSON
        utils.save_json("running_coops", running_coops)

        # Updates archive JSON
        archive = utils.read_json("participation_archive")
        archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(ctx_author.id)] = "yes"
        utils.save_json("participation_archive", archive)

        # Responds to the interaction
        await ctx.send("Coop registered :white_check_mark:", ephemeral=True)

    #endregion

    #region Slash commands (coop channels)

    @interactions.extension_command(
        name="lock",
        description="Locks a coop, preventing people from joining",
        scope=GUILD_IDS
    )
    # TODO Owner, admin, coop organizer and coop creator permissions
    async def lock_coop(self, ctx: CommandContext):

        if not (coop_infos_tuple := checks.check_coop_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if running_coops[contract_id]["coops"][coop_nb-1]["locked"]:
            await ctx.send(":warning: Coop is already locked", ephemeral=True)
            return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))
        
        channel = pycord.utils.get(ctx_guild.channels, id=running_coops[contract_id]["channel_id"])
        coop_message = await channel.fetch_message(running_coops[contract_id]["coops"][coop_nb-1]["message_id"])
        locked_button = interactions.Button(
            style=interactions.ButtonStyle.DANGER,
            label="LOCKED",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=True
        )
        await coop_message.edit(components=locked_button)

        running_coops[contract_id]["coops"][coop_nb-1]["locked"] = True
        utils.save_json("running_coops", running_coops)
        
        # Responds to the interaction
        await ctx.send("Coop locked :white_check_mark:", ephemeral=True)
    
    @interactions.extension_command(
        name="unlock",
        description="Unlocks a coop, allowing people to join again",
        scope=GUILD_IDS
    )
    # TODO Owner, admin, coop organizer and coop creator permissions
    async def unlock_coop(self, ctx: CommandContext):

        if not (coop_infos_tuple := checks.check_coop_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if not running_coops[contract_id]["coops"][coop_nb-1]["locked"]:
            await ctx.send(":warning: Coop is already unlocked", ephemeral=True)
            return

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))
        
        channel = pycord.utils.get(ctx_guild.channels, id=running_coops[contract_id]["channel_id"])
        coop_message = await channel.fetch_message(running_coops[contract_id]["coops"][coop_nb-1]["message_id"])
        
        is_full = len(running_coops[contract_id]["coops"][coop_nb-1]["members"]) == running_coops[contract_id]["size"]
        join_button = interactions.Button(
            style=interactions.ButtonStyle.SUCCESS,
            label="Join",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=is_full
        )
        await coop_message.edit(components=join_button)

        running_coops[contract_id]["coops"][coop_nb-1]["locked"] = False
        utils.save_json("running_coops", running_coops)
        
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
    # TODO Owner, admin, coop organizer and coop creator permissions
    async def kick_from_coop(self, ctx: CommandContext, member: interactions.Member):

        if not (coop_infos_tuple := checks.check_coop_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))

        alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")

        # If user has left the guild, member is passed as user ID
        if type(member) != interactions.Member:
            member = await self.bot._http.get_user(member)
            member_id = int(member.user.id)
            ctx_send = ctx
        # Check for alt
        elif alt_role in member.roles:
                alt_dic = utils.read_json("alt_index")
                action_row = interactions.ActionRow(
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{alt_dic[str(member.id)]['main']}",
                        custom_id=f"main-{uuid.uuid4()}"
                    ),
                    interactions.Button(
                        style=interactions.ButtonStyle.SECONDARY,
                        label=f"{alt_dic[str(member.id)]['alt']}",
                        custom_id=f"alt-{uuid.uuid4()}"
                    )
                )
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
            running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]
            and self.pycord_bot.owner_id != ctx_author.id
            and not ctx_author.guild_permissions.administrator
        ):
            await ctx_send.send(":warning: Coop is completed or failed", ephemeral=True)
            return
        if member_id not in running_coops[contract_id]["coops"][coop_nb-1]["members"]:
            await ctx_send.send(":warning: Member is not in this coop", ephemeral=True)
            return
        if member_id == running_coops[contract_id]["coops"][coop_nb-1]["creator"]:
            await ctx_send.send(":warning: You can't kick the coop creator", ephemeral=True)
            return

        # Updates running_coops JSON
        running_coops[contract_id]["coops"][coop_nb-1]["members"].remove(member_id)
        running_coops[contract_id]["remaining"].append(member_id)

        # Updates coop message
        coop_dic = running_coops[contract_id]["coops"][coop_nb-1]
        channel = pycord.utils.get(ctx_guild.channels, id=running_coops[contract_id]["channel_id"])
        coop_message = await channel.fetch_message(coop_dic["message_id"])
        
        other_members_mentions = []
        for id in coop_dic["members"]:
            if id != coop_dic["creator"]:
                other_members_mentions.append(await utils.get_member_mention(id, ctx_guild, self.pycord_bot))

        coop_embed = None
        coop_content = None
        if utils.read_guild_config(ctx_guild.id, "USE_EMBEDS"):
            coop_embed = utils.get_coop_embed(
                coop_nb,
                running_coops[contract_id]['size'],
                await utils.get_member_mention(coop_dic['creator'], ctx_guild, self.pycord_bot),
                other_members_mentions,
                coop_message.embeds[0].color if coop_message.embeds else pycord.Color.random()
            )
        else:
            coop_content = utils.get_coop_content(
                coop_nb,
                running_coops[contract_id]['size'],
                await utils.get_member_mention(coop_dic['creator'], ctx_guild, self.pycord_bot),
                other_members_mentions
            )

        if coop_dic["locked"]:
            button = interactions.Button(
                style=interactions.ButtonStyle.DANGER,
                label="LOCKED",
                custom_id=f"joincoop_{contract_id}_{coop_nb}",
                disabled=True
            )
        else:
            button = interactions.Button(
                style=interactions.ButtonStyle.SUCCESS,
                label="Join",
                custom_id=f"joincoop_{contract_id}_{coop_nb}",
                disabled=False
            )

        await coop_message.edit(content=coop_content, embed=coop_embed, components=button)

        # Updates contract message
        contract_message = await channel.fetch_message(running_coops[contract_id]["message_id"])

        remaining_mentions = []
        for id in running_coops[contract_id]["remaining"]:
            remaining_mentions.append(await utils.get_member_mention(id, ctx_guild, self.pycord_bot))
        
        remaining_index = contract_message.content.index("**Remaining:")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})**\n{''.join(remaining_mentions)}\n"
        await contract_message.edit(content=new_contract_content)

        # Removes coop role to remove access to coop channel
        if str(member_id).startswith("alt"):
            discord_id = member_id.replace("alt", "")
        else:
            discord_id = member_id
        if type(member) == interactions.Member:
            await ctx_guild.get_member(discord_id).remove_roles(pycord.utils.get(ctx_guild.roles, name=f"{contract_id}-{coop_nb}"))

        # Saves JSON
        utils.save_json("running_coops", running_coops)

        # Updates archive JSON
        archive = utils.read_json("participation_archive")
        archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member_id)] = "no"
        utils.save_json("participation_archive", archive)
        
        # Responds to the interaction
        await ctx_send.send(f"{member.mention} kicked from coop :white_check_mark:", ephemeral=True)
   
    @interactions.extension_command(
        name="coop-completed",
        description="Marks the coop as completed",
        scope=GUILD_IDS
    )
    # TODO Owner, admin, coop organizer and coop creator permissions
    async def coop_completed_slash(self, ctx: ComponentContext):
        
        if not (coop_infos_tuple := checks.check_coop_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        
        await self.execute_coop_completed(ctx_guild, contract_id, coop_nb)
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as completed :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="coop-failed",
        description="Marks the coop as failed. Returns members to the remaining list",
        scope=GUILD_IDS
    )
    # TODO Owner, admin, coop organizer and coop creator permissions
    async def coop_failed_slash(self, ctx: CommandContext):
        
        if not (coop_infos_tuple := checks.check_coop_channel(int(ctx.channel_id))):
            await ctx.send(":warning: Not a coop channel", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        
        await self.execute_coop_failed(ctx_guild, contract_id, coop_nb)
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as failed :white_check_mark:", ephemeral=True)

    #endregion

    #region Context menus
    
    @interactions.extension_command(
        name="Coop completed",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    # TODO @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), is_coop_creator_context_menu())
    async def coop_completed_menu(self, ctx: ComponentContext):
        
        if not (coop_infos_tuple := checks.check_context_menu_coop_message(int(ctx.target.id))):
            await ctx.send(":warning: Not a coop message", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple
        
        running_coops = utils.read_json("running_coops")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return

        await self.execute_coop_completed(ctx_guild, contract_id, coop_nb)
        
        # Responds to the interaction
        await ctx.send(f"Marked the coop as completed :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="Coop failed",
        scope=GUILD_IDS,
        type=interactions.ApplicationCommandType.MESSAGE
    )
    # TODO @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), is_coop_creator_context_menu())
    async def coop_failed(self, ctx: ComponentContext):
        
        if not (coop_infos_tuple := checks.check_context_menu_coop_message(int(ctx.target.id))):
            await ctx.send(":warning: Not a coop message", ephemeral=True)
            return
        contract_id, coop_nb = coop_infos_tuple

        running_coops = utils.read_json("running_coops")
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))

        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", ephemeral=True)
            return

        await self.execute_coop_failed(ctx_guild, contract_id, coop_nb)

        # Responds to the interaction
        await ctx.send(f"Marked the coop as failed :white_check_mark:", ephemeral=True)

    #endregion

    #region Events

    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):
        utils = ctx.bot.get_cog("Utils")

        # Join coop button
        if ctx.custom_id.startswith("joincoop_"):
            contract_id = ctx.custom_id.split('_')[1]
            coop_nb = int(ctx.custom_id.split('_')[2])

            author_id = ctx.author.id
            is_alt = False

            # Check for alt
            alt_dic = utils.read_json("alt_index")
            alt_role = discord.utils.get(ctx.guild.roles, name="Alt")
            if alt_role in ctx.author.roles:
                action_row = create_actionrow(
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(ctx.author.id)]['main']}",
                                                    custom_id=f"main-{uuid.uuid4()}"
                                                ),
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(ctx.author.id)]['alt']}",
                                                    custom_id=f"alt-{uuid.uuid4()}"
                                                )
                                            )
                await ctx.send("Which account is joining ?", components=[action_row], ephemeral=True)

                try:
                    ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row, timeout=10)
                except asyncio.TimeoutError:
                    await ctx.send("Action cancelled :negative_squared_cross_mark:", ephemeral=True)
                    return
                if ctx_alt.custom_id.startswith("alt"):
                    author_id = "alt" + str(ctx.author.id)
                    is_alt = True
                ctx_send = ctx_alt
            else:
                ctx_send = ctx

            # General checks
            running_coops = utils.read_json("running_coops")
            if "already_done" in running_coops[contract_id].keys() and author_id in running_coops[contract_id]["already_done"]:
                await ctx_send.send("You have already completed this contract :smile:", ephemeral=True)
                return
            for coop in running_coops[contract_id]["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", ephemeral=True)
                    return
            
            prev_remaining_count = len(running_coops[contract_id]["remaining"])
            # If AFK and joins a coop, removes AFK role
            if author_id not in running_coops[contract_id]["remaining"]:
                afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
                if not is_alt and afk_role in ctx.author.roles: # Alt doesn't count for AFK
                    await ctx.author.remove_roles(afk_role)
            # Updates running_coops JSON
            else:
                running_coops[contract_id]["remaining"].remove(author_id)
            running_coops[contract_id]["coops"][coop_nb-1]["members"].append(author_id)

            # Notif to coop organizers, only if remaining wasn't already empty
            if len(running_coops[contract_id]["remaining"]) == 0 and prev_remaining_count > 0:
                await self.send_notif_no_remaining(ctx.guild, contract_id)

            # Updates archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(author_id)] = "yes"

            # Updates contract message
            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(await utils.get_member_mention(id, ctx.guild, self.bot))
                
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            contract_message = await channel.fetch_message(running_coops[contract_id]["message_id"])
            remaining_index = contract_message.content.index("**Remaining:")
            new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})**\n{''.join(remaining_mentions)}\n"
            await contract_message.edit(content=new_contract_content)

            # Updates coop message
            coop_dic = running_coops[contract_id]["coops"][coop_nb-1].copy()

            other_members_mentions = []
            for id in coop_dic["members"]:
                if id != coop_dic["creator"]:
                    other_members_mentions.append(await utils.get_member_mention(id, ctx.guild, self.bot))

            coop_embed = None
            coop_content = None
            if utils.read_guild_config(ctx.guild.id, "USE_EMBEDS"):
                coop_embed = utils.get_coop_embed(coop_nb,
                                                    running_coops[contract_id]['size'],
                                                    await utils.get_member_mention(coop_dic['creator'], ctx.guild, self.bot),
                                                    other_members_mentions,
                                                    ctx.origin_message.embeds[0].color if ctx.origin_message.embeds else discord.Color.random()
                                                    )
            else:
                coop_content = utils.get_coop_content(coop_nb,
                                                        running_coops[contract_id]['size'],
                                                        await utils.get_member_mention(coop_dic['creator'], ctx.guild, self.bot),
                                                        other_members_mentions
                                                        )

            action_row = [create_actionrow(create_button(style=ButtonStyle.green,
                                                        label="Join",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                        disabled=(len(coop_dic["members"]) == running_coops[contract_id]['size'])
                                                        ))]
            await ctx.origin_message.edit(content=coop_content, embed=coop_embed, components=action_row)

            # Gives coop role for access to coop channel
            await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name=f"{contract_id}-{coop_nb}"))

            # Saves JSONs
            utils.save_json("running_coops", running_coops)
            utils.save_json("participation_archive", archive)

            # Sends coop code in hidden message
            await ctx_send.send(f"Code to join **Coop {coop_nb}** is: `{coop_dic['code']}`\n" +
                                "Don't forget to activate your deflector and ship in bottle :wink:", ephemeral=True)
        

    #endregion

    #region Misc methods

    async def execute_coop_completed(self, guild: pycord.Guild, contract_id, coop_nb):
        
        running_coops = utils.read_json("running_coops")

        # Deletes coop role and coop channel
        if not utils.read_guild_config(guild.id, "KEEP_COOP_CHANNELS"):
            await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()

            for channel in pycord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"]).category.text_channels:
                if channel.name == f"coop-{coop_nb}":
                    await channel.delete()
                    break

        # Updates coop message
        channel = pycord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"])
        coop_message = await channel.fetch_message(running_coops[contract_id]["coops"][coop_nb-1]["message_id"])
        
        completed_button = interactions.Button(
            style=interactions.ButtonStyle.PRIMARY,
            label="COMPLETED",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=True
        )
        await coop_message.edit(components=completed_button)

        # Removes coop creator role
        creator = guild.get_member(running_coops[contract_id]["coops"][coop_nb-1]["creator"])
        # If creator has not left the guild
        if creator != None:
            keep_role = False
            for id, contract in running_coops.items():
                for i in range(len(contract["coops"])):
                    if contract["coops"][i]["creator"] == creator.id and id != contract_id and not contract["coops"][i]["completed_or_failed"]:
                        keep_role = True
            if not keep_role:
                await creator.remove_roles(pycord.utils.get(guild.roles, name="Coop Creator"))

        # Updates running_coops JSON
        running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"] = True
        utils.save_json("running_coops", running_coops)

    async def execute_coop_failed(self, guild: pycord.Guild, contract_id, coop_nb):
        
        running_coops = utils.read_json("running_coops")

        # Removes coop creator role
        creator = guild.get_member(running_coops[contract_id]["coops"][coop_nb-1]["creator"])
        # If creator has not left the guild
        if creator != None:
            keep_role = False
            for id, contract in running_coops.items():
                for i in range(len(contract["coops"])):
                    if contract["coops"][i]["creator"] == creator.id and id != contract_id and not contract["coops"][i]["completed_or_failed"]:
                        keep_role = True
            if not keep_role:
                await creator.remove_roles(pycord.utils.get(guild.roles, name="Coop Creator"))

        # Updates running_coops and archive JSONs
        archive = utils.read_json("participation_archive")

        running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"] = True
        running_coops[contract_id]["coops"][coop_nb-1]["creator"] = ""

        for member_id in running_coops[contract_id]["coops"][coop_nb-1]["members"]:
            running_coops[contract_id]["remaining"].append(member_id)
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member_id)] = "no"
        running_coops[contract_id]["coops"][coop_nb-1]["members"] = []

        # Deletes coop role and coop channel
        if not utils.read_guild_config(guild.id, "KEEP_COOP_CHANNELS"):
            await pycord.utils.get(guild.roles, name=f"{contract_id}-{coop_nb}").delete()

            for channel in pycord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"]).category.text_channels:
                if channel.name == f"coop-{coop_nb}":
                    await channel.delete()
                    break

        # Updates coop message
        contract_channel = pycord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"])
        coop_message = await contract_channel.fetch_message(running_coops[contract_id]["coops"][coop_nb-1]["message_id"])

        coop_embed = None
        coop_content = None
        if utils.read_guild_config(guild.id, "USE_EMBEDS"):
            coop_embed = utils.get_coop_embed(
                coop_nb,
                running_coops[contract_id]['size'],
                color=coop_message.embeds[0].color if coop_message.embeds else pycord.Color.random()
            )
        else:
            coop_content = utils.get_coop_content(coop_nb, running_coops[contract_id]['size'])

        failed_button = interactions.Button(
            style=interactions.ButtonStyle.DANGER,
            label="FAILED",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=True
        )
        await coop_message.edit(content=coop_content, embed=coop_embed, components=failed_button)

        # Updates contract message
        contract_message = await contract_channel.fetch_message(running_coops[contract_id]["message_id"])

        remaining_mentions = []
        for id in running_coops[contract_id]["remaining"]:
            remaining_mentions.append(await utils.get_member_mention(id, guild, self.bot))
        
        remaining_index = contract_message.content.index("**Remaining:")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})**\n{''.join(remaining_mentions)}\n"
        await contract_message.edit(content=new_contract_content)

        # Saves JSONs
        utils.save_json("running_coops", running_coops)
        utils.save_json("participation_archive", archive)

    #endregion

def setup(bot, pycord_bot):
    Coop(bot, pycord_bot)
