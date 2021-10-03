import discord
from discord.ext import commands

from discord_slash import cog_ext
from discord_slash.context import *
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import *
from discord_slash.model import *

import json
from datetime import date

with open("config.json", "r") as f:
    config = json.load(f)
    if config["guilds"]:
        GUILD_IDS = list(map(int, config["guilds"].keys()))
    else:
        GUILD_IDS = []

class Coop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog("Utils")


    #########################
    ##### Check methods #####
    #########################

    def is_bot_channel():
        def predicate(ctx):
            return ctx.channel.id == ctx.bot.get_cog("Utils").get_bot_channel_id(ctx.guild.id)
        return commands.check(predicate)

    def is_not_afk():
        def predicate(ctx):
            afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
            return afk_role not in ctx.author.roles
        return commands.check(predicate)
    
    def is_coop_creator_context_menu():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops.values():
                for coop in contract["coops"]:
                    if ctx.target_message.id == coop["message_id"] and ctx.author.id == coop["creator"]:
                        return True
            return False
        return commands.check(predicate)
    
    def check_context_menu_target_contract():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops.values():
                if ctx.target_message.id == contract["message_id"]:
                    return True
            return False
        return commands.check(predicate)

    def check_context_menu_target_coop():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops.values():
                for coop in contract["coops"]:
                    if ctx.target_message.id == coop["message_id"]:
                        return True
            return False
        return commands.check(predicate)


    ##########################
    ##### Slash Commands #####
    ##########################
    
    @cog_ext.cog_slash(name="contract",
                        description="Registers a new contract and creates a channel and category for it",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The unique ID for an EggInc contract",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="size",
                                description="Number of slots available in the contract",
                                option_type=SlashCommandOptionType.INTEGER,
                                required=True
                            ),
                            create_option(
                                name="is_leggacy",
                                description="Whether the contract is leggacy or not",
                                option_type=SlashCommandOptionType.BOOLEAN,
                                required=True
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"))
    async def add_contract(self, ctx: SlashContext, contract_id: str, size: int, is_leggacy: bool):
        
        running_coops = self.utils.read_json("running_coops")
        archive = self.utils.read_json("participation_archive")

        if contract_id in running_coops.keys():
            await ctx.send(":warning: Contract already exists", hidden=True)
            return
        if not is_leggacy and contract_id in archive.keys():
            await ctx.send(":warning: Contract has to be a leggacy. Already registered in archive", hidden=True)
            return
        if size <= 1:
            await ctx.send(":warning: Invalid contract size", hidden=True)
            return
        
        # Creates a category and channel below commands channel for the contract, where coops will be listed
        category = await ctx.guild.create_category(contract_id)
        await category.move(after=ctx.channel.category)

        channel_overwrites = ctx.channel.overwrites.copy()
        if ctx.guild.default_role in channel_overwrites.keys():
            channel_overwrites[ctx.guild.default_role].update(view_channel=False)
        else:
            channel_overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        
        for role_name in [self.bot.user.name, "Coop Organizer", "Coop Creator"]:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role in channel_overwrites.keys():
                channel_overwrites[role].update(view_channel=True, send_messages=True)
            else:
                channel_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

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
        
        guest_role = ctx.guild.get_role(self.utils.read_guild_config(ctx.guild.id, "GUEST_ROLE_ID"))
        afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
        alt_role = discord.utils.get(ctx.guild.roles, name="Alt")
        remaining_ids = []
        already_done_ids = []
        afk_ids = []
        for member in ctx.guild.members:
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
                        + (f"**Already done:** {''.join([await self.utils.get_member_mention(id, ctx.guild, self.bot) for id in already_done_ids])}\n\n" if is_leggacy else "")
                        + f"**Remaining: ({len(remaining_ids)})** {''.join([await self.utils.get_member_mention(id, ctx.guild, self.bot) for id in remaining_ids])}\n "
                        )
        if is_leggacy:
            action_row = [create_actionrow(create_button(style=ButtonStyle.blurple, label="I've already done this contract", custom_id=f"leggacy_{contract_id}"))]
        else:
            action_row = None
        message = await channel.send(contract_string, components=action_row)
        
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
        self.utils.save_json("running_coops", running_coops)

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
        self.utils.save_json("participation_archive", archive)

        # Responds to the interaction
        await ctx.send("Contract registered :white_check_mark:", hidden=True)
    
    @cog_ext.cog_slash(name="coop",
                        description="Registers a new coop and displays it in the contract channel",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The unique ID for an EggInc contract",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="coop_code",
                                description="The code to join the coop",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="locked",
                                description="Whether or not the coop is locked at creation. Prevents people from joining",
                                option_type=SlashCommandOptionType.BOOLEAN,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @is_not_afk()
    async def add_coop(self, ctx: SlashContext, contract_id: str, coop_code: str, locked: bool=False):
        
        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if "already_done" in running_coops[contract_id].keys() and ctx.author.id in running_coops[contract_id]["already_done"]:
            await ctx.send("You have already completed this contract :smile:", hidden=True)
            return
        for coop in running_coops[contract_id]["coops"]:
            if ctx.author.id in coop["members"]:
                await ctx.send("You have already joined a coop for this contract :smile:", hidden=True)
                return

        # Creates coop message with join button
        coop_nb = len(running_coops[contract_id]["coops"]) + 1
        contract_channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
        action_row = [create_actionrow(create_button(style=ButtonStyle.green,
                                                    label=f"{'LOCKED' if locked else 'Join'}",
                                                    custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                    disabled=locked
                                                    ))]
        coop_embed = discord.Embed(color=discord.Color.random(),
                                    title=f"Coop {coop_nb} - 1/{running_coops[contract_id]['size']}",
                                    description=f"**Members:**\n- {ctx.author.mention} (Creator)\n"
                                    )
        message = await contract_channel.send(embed=coop_embed, components=action_row)

        # Creates coop channel and role
        coop_role = await ctx.guild.create_role(name=f"{contract_id}-{coop_nb}")
        coop_channel = await contract_channel.category.create_text_channel(f"coop-{coop_nb}",
                                                                    overwrites={
                                                                        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                                                        discord.utils.get(ctx.guild.roles, name=self.bot.user.name): discord.PermissionOverwrite(view_channel=True),
                                                                        discord.utils.get(ctx.guild.roles, name="Coop Organizer"): discord.PermissionOverwrite(view_channel=True),
                                                                        coop_role: discord.PermissionOverwrite(view_channel=True),
                                                                    })
        to_pin = await coop_channel.send(":x: Do not share the coop code with anyone outside of this coop\n" +
                        ":x: Do not make the coop public unless told by a coop organizer\n\n" +
                        f"Coop code: `{coop_code}`"
                        )
        await to_pin.pin()
        await ctx.author.add_roles(coop_role)

        # Updates running_coops JSON
        coop_dic = {
            "code": coop_code,
            "creator": ctx.author.id,
            "message_id": message.id,
            "locked": locked,
            "completed_or_failed": False,
            "members": [ctx.author.id]
        }
        running_coops[contract_id]["coops"].append(coop_dic)
        running_coops[contract_id]["remaining"].remove(ctx.author.id)
        self.utils.save_json("running_coops", running_coops)

        # Gives coop creator role
        await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name="Coop Creator"))

        # Notif to coop organizers
        if len(running_coops[contract_id]["remaining"]) == 0:
            await self.send_notif_no_remaining(ctx.guild, contract_id)

        # Updates archive JSON
        archive = self.utils.read_json("participation_archive")
        archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(ctx.author.id)] = "yes"
        self.utils.save_json("participation_archive", archive)

        # Updates contract message
        remaining_mentions = []
        for id in running_coops[contract_id]["remaining"]:
            remaining_mentions.append(await self.utils.get_member_mention(id, ctx.guild, self.bot))
        
        contract_message = await contract_channel.fetch_message(running_coops[contract_id]["message_id"])
        remaining_index = contract_message.content.index("**Remaining:")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})** {''.join(remaining_mentions)}\n"
        await contract_message.edit(content=new_contract_content)

        # Responds to the interaction
        await ctx.send("Coop registered :white_check_mark:", hidden=True)

    @cog_ext.cog_slash(name="lock",
                        description="Locks a coop, preventing people from joining",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The unique ID for an EggInc contract",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="coop_nb",
                                description="The number of the coop. If not given, looks for the coop of which you are the creator",
                                option_type=SlashCommandOptionType.INTEGER,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), commands.has_role("Coop Creator"))
    async def lock_coop(self, ctx: SlashContext, contract_id: str, coop_nb: int=None):

        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx.send(":warning: Invalid coop number", hidden=True)
                return
            if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
                await ctx.send(":warning: Coop is completed or failed", hidden=True)
                return
            if running_coops[contract_id]["coops"][coop_nb-1]["locked"]:
                await ctx.send(":warning: Coop is already locked", hidden=True)
                return

        is_author_creator = False
        for i in range(len(running_coops[contract_id]["coops"])):
            if running_coops[contract_id]["coops"][i]["creator"] == ctx.author.id:
                is_author_creator = True
                creator_coop_nb = i + 1
        
        async def lock(coop_nb_to_lock):
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            coop_message = await channel.fetch_message(running_coops[contract_id]["coops"][coop_nb_to_lock-1]["message_id"])
            action_row = [create_actionrow(create_button(style=ButtonStyle.red,
                                                        label="LOCKED",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb_to_lock}",
                                                        disabled=True
                                                        ))]
            await coop_message.edit(embed=coop_message.embeds[0], components=action_row)

            running_coops[contract_id]["coops"][coop_nb_to_lock-1]["locked"] = True
            self.utils.save_json("running_coops", running_coops)
        
        if coop_nb != None:
            coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
            if ((is_author_creator and creator_coop_nb == coop_nb)
                    or self.bot.owner_id == ctx.author.id
                    or ctx.author.guild_permissions.administrator
                    or coop_role in ctx.author.roles):
                await lock(coop_nb)
            else:
                await ctx.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
                if running_coops[contract_id]["coops"][creator_coop_nb-1]["completed_or_failed"]:
                    await ctx.send(":warning: Coop is completed or failed", hidden=True)
                    return
                await lock(creator_coop_nb)
            else:
                await ctx.send(f":warning: You are not creator of any coop for contract `{contract_id}`", hidden=True)
                return
        
        # Responds to the interaction
        await ctx.send("Coop locked :white_check_mark:", hidden=True)
    
    @cog_ext.cog_slash(name="unlock",
                        description="Unlocks a coop, allowing people to join again",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The unique ID for an EggInc contract",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="coop_nb",
                                description="The number of the coop. If not given, looks for the coop of which you are the creator",
                                option_type=SlashCommandOptionType.INTEGER,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), commands.has_role("Coop Creator"))
    async def unlock_coop(self, ctx: SlashContext, contract_id: str, coop_nb: int=None):

        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx.send(":warning: Invalid coop number", hidden=True)
                return
            if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
                await ctx.send(":warning: Coop is completed or failed", hidden=True)
                return
            if not running_coops[contract_id]["coops"][coop_nb-1]["locked"]:
                await ctx.send(":warning: Coop is already unlocked", hidden=True)
                return

        is_author_creator = False
        for i in range(len(running_coops[contract_id]["coops"])):
            if running_coops[contract_id]["coops"][i]["creator"] == ctx.author.id:
                is_author_creator = True
                creator_coop_nb = i + 1
        
        async def unlock(coop_nb_to_unlock):
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            coop_message = await channel.fetch_message(running_coops[contract_id]["coops"][coop_nb_to_unlock-1]["message_id"])
            
            is_full = len(running_coops[contract_id]["coops"][coop_nb_to_unlock-1]["members"]) == running_coops[contract_id]["size"]
            action_row = [create_actionrow(create_button(style=ButtonStyle.green,
                                                        label="Join",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb_to_unlock}",
                                                        disabled=is_full
                                                        ))]
            await coop_message.edit(embed=coop_message.embeds[0], components=action_row)

            running_coops[contract_id]["coops"][coop_nb_to_unlock-1]["locked"] = False
            self.utils.save_json("running_coops", running_coops)
        
        if coop_nb != None:
            coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
            if ((is_author_creator and creator_coop_nb == coop_nb) 
                    or self.bot.owner_id == ctx.author.id
                    or ctx.author.guild_permissions.administrator
                    or coop_role in ctx.author.roles):
                await unlock(coop_nb)
            else:
                await ctx.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
                if running_coops[contract_id]["coops"][creator_coop_nb-1]["completed_or_failed"]:
                    await ctx.send(":warning: Coop is completed or failed", hidden=True)
                    return
                await unlock(creator_coop_nb)
            else:
                await ctx.send(f":warning: You are not creator of any coop for contract `{contract_id}`", hidden=True)
                return
        
        # Responds to the interaction
        await ctx.send("Coop unlocked :white_check_mark:", hidden=True)

    @cog_ext.cog_slash(name="kick",
                        description="Kicks someone from a coop",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="member",
                                description="The member to be kicked from the coop",
                                option_type=SlashCommandOptionType.USER,
                                required=True
                            ),
                            create_option(
                                name="contract_id",
                                description="The unique ID for an EggInc contract",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="coop_nb",
                                description="The number of the coop. If not given, looks for the coop of which you are the creator",
                                option_type=SlashCommandOptionType.INTEGER,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), commands.has_role("Coop Creator"))
    async def kick_from_coop(self, ctx: SlashContext, member: discord.Member, contract_id: str, coop_nb: int=None):

        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return

        alt_role = discord.utils.get(ctx.guild.roles, name="Alt")

        # If user has left the guild, member is passed as user ID
        if type(member) != discord.Member:
            member = await self.bot.fetch_user(member)
            member_id = member.id
            ctx_send = ctx
        # Check for alt
        elif alt_role in member.roles:
                alt_dic = self.utils.read_json("alt_index")
                action_row = create_actionrow(
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(member.id)]['main']}",
                                                    custom_id="main"
                                                ),
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(member.id)]['alt']}",
                                                    custom_id="alt"
                                                )
                                            )
                await ctx.send("Which account do you want to kick ?", components=[action_row], hidden=True)

                ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row)
                if ctx_alt.custom_id == "alt":
                    member_id = "alt" + str(member.id)
                ctx_send = ctx_alt
        else:
            member_id = member.id
            ctx_send = ctx
        
        if (member_id in running_coops[contract_id]["remaining"]
            or ("already_done" in running_coops[contract_id].keys() and member_id in running_coops[contract_id]["already_done"])):
            await ctx_send.send(":warning: Member is not in a coop for this contract", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx_send.send(":warning: Invalid coop number", hidden=True)
                return
            if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
                await ctx_send.send(":warning: Coop is completed or failed", hidden=True)
                return
            if member_id not in running_coops[contract_id]["coops"][coop_nb-1]["members"]:
                await ctx_send.send(":warning: Member is not in this coop", hidden=True)
                return

        is_author_creator = False
        for i in range(len(running_coops[contract_id]["coops"])):
            if running_coops[contract_id]["coops"][i]["creator"] == ctx.author.id:
                is_author_creator = True
                creator_coop_nb = i + 1

        async def kick(from_coop_nb):
            # Updates running_coops JSON
            running_coops[contract_id]["coops"][from_coop_nb-1]["members"].remove(member_id)
            running_coops[contract_id]["remaining"].append(member_id)
            self.utils.save_json("running_coops", running_coops)

            # Updates coop message
            coop_dic = running_coops[contract_id]["coops"][from_coop_nb-1]
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            coop_message = await channel.fetch_message(coop_dic["message_id"])
            
            coop_embed = coop_message.embeds[0]
            coop_embed.title = f"Coop {from_coop_nb} - {len(coop_dic['members'])}/{running_coops[contract_id]['size']}"
            desc = f"**Members:**\n- {ctx.guild.get_member(coop_dic['creator']).mention} (Creator)\n"
            for id in coop_dic["members"]:
                if id == coop_dic["creator"]:
                    continue
                desc = desc + f"- {await self.utils.get_member_mention(id, ctx.guild, self.bot)}\n"
            coop_embed.description = desc

            action_row = [create_actionrow(create_button(style=ButtonStyle.red if coop_dic["locked"] else ButtonStyle.green,
                                                        label="LOCKED" if coop_dic["locked"] else "Join",
                                                        custom_id=f"joincoop_{contract_id}_{from_coop_nb}",
                                                        disabled=coop_dic["locked"]
                                                        ))]
            await coop_message.edit(embed=coop_embed, components=action_row)

            # Updates contract message
            contract_message = await channel.fetch_message(running_coops[contract_id]["message_id"])

            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(await self.utils.get_member_mention(id, ctx.guild, self.bot))
            
            remaining_index = contract_message.content.index("**Remaining:")
            new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})** {''.join(remaining_mentions)}\n"
            await contract_message.edit(content=new_contract_content)

            # Updates archive JSON
            archive = self.utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member_id)] = "no"
            self.utils.save_json("participation_archive", archive)

            # Removes coop role to remove access to coop channel
            if str(member_id).startswith("alt"):
                discord_id = member_id.replace("alt", "")
            else:
                discord_id = member_id
            if type(member) == discord.Member:
                await ctx.guild.get_member(discord_id).remove_roles(discord.utils.get(ctx.guild.roles, name=f"{contract_id}-{from_coop_nb}"))
        
        if coop_nb != None:
            if is_author_creator and creator_coop_nb == coop_nb and member == ctx.author:
                await ctx_send.send(":warning: You can't kick yourself as a coop creator", hidden=True)
                return
            coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
            if ((is_author_creator and creator_coop_nb == coop_nb)
                    or self.bot.owner_id == ctx.author.id
                    or ctx.author.guild_permissions.administrator
                    or coop_role in ctx.author.roles):
                if member_id == running_coops[contract_id]["coops"][coop_nb-1]["creator"]:
                    await ctx_send.send(":warning: You can't kick the coop creator", hidden=True)
                    return
                await kick(coop_nb)
            else:
                await ctx_send.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
                if running_coops[contract_id]["coops"][creator_coop_nb-1]["completed_or_failed"]:
                    await ctx_send.send(":warning: Coop is completed or failed", hidden=True)
                    return
                if member == ctx.author:
                    await ctx_send.send(":warning: You can't kick yourself as a coop creator", hidden=True)
                    return
                if member_id in running_coops[contract_id]["coops"][creator_coop_nb-1]["members"]:
                    await kick(creator_coop_nb)
                else:
                    await ctx_send.send(f":warning: Member is not in the coop you created (Coop {creator_coop_nb})", hidden=True)
                    return
            else:
                await ctx_send.send(f":warning: You are not creator of any coop for contract `{contract_id}`", hidden=True)
                return
        
        # Responds to the interaction
        await ctx_send.send(f"{member.mention} kicked from coop :white_check_mark:", hidden=True)
    
    @cog_ext.cog_slash(name="codes",
                        description="Sends the codes of currently running coops",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The contract for which you want the coop codes. If not given, sends for all running contracts",
                                option_type=SlashCommandOptionType.STRING,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"))
    async def get_coop_codes(self, ctx: SlashContext, contract_id: str=""):

        running_coops = self.utils.read_json("running_coops")

        if contract_id:
            if contract_id not in running_coops.keys():
                await ctx.send(":warning: Contract does not exist or is not currently running", hidden=True)
                return
            contract_ids = [contract_id]
        else:
            contract_ids = running_coops.keys()
        
        message = "__**Coop codes:**__\n"
        for id in contract_ids:
            message = message + "\n" + f"**Contract `{id}`:**\n"
            for i in range(len(running_coops[id]["coops"])):
                message = message + f"- Coop {i+1}: `{running_coops[id]['coops'][i]['code']}`\n"

        await ctx.send(message, hidden=True)

    @cog_ext.cog_slash(name="register-alt",
                        description="Registers an alt EggInc account for the Discord account",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="member",
                                description="The Discord account",
                                option_type=SlashCommandOptionType.USER,
                                required=True
                            ),
                            create_option(
                                name="name_main",
                                description="The EggInc name of the main account",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            ),
                            create_option(
                                name="name_alt",
                                description="The EggInc name of the alt account",
                                option_type=SlashCommandOptionType.STRING,
                                required=True
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def register_alt_account(self, ctx: SlashContext, member: discord.Member, name_main: str, name_alt: str):
        
        if type(member) != discord.Member:
            await ctx.send(":warning: This user is not in the guild", hidden=True)
            return
        alt_role = discord.utils.get(ctx.guild.roles, name="Alt")
        if alt_role in member.roles:
            await ctx.send(":warning: This user already has an alt account", hidden=True)
            return

        alt_dic = self.utils.read_json("alt_index")
        alt_dic[str(member.id)] = {
            "main": name_main,
            "alt": name_alt
        }
        self.utils.save_json("alt_index", alt_dic)
        await member.add_roles(alt_role)

        await ctx.send("Alt account registered :white_check_mark:", hidden=True)

    @cog_ext.cog_slash(name="unregister-alt",
                        description="Unregisters the alt EggInc account for the Discord account",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="member",
                                description="The Discord account",
                                option_type=SlashCommandOptionType.USER,
                                required=True
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def unregister_alt_account(self, ctx: SlashContext, member: discord.Member):

        if type(member) != discord.Member:
            await ctx.send(":warning: This user is not in the guild", hidden=True)
            return
        alt_role = discord.utils.get(ctx.guild.roles, name="Alt")
        if alt_role not in member.roles:
            await ctx.send(":warning: This user has no alt account", hidden=True)
            return

        alt_dic = self.utils.read_json("alt_index")
        alt_dic.pop(str(member.id))
        self.utils.save_json("alt_index", alt_dic)
        await member.remove_roles(alt_role)

        await ctx.send("Alt account unregistered :white_check_mark:", hidden=True)


    #########################
    ##### Context Menus #####
    #########################

    @cog_ext.cog_context_menu(name="Remove contract",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_contract()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"))
    async def remove_contract(self, ctx: MenuContext):
        
        running_coops = self.utils.read_json("running_coops")
        with open("config.json", "r") as f:
            config = json.load(f)
            COOPS_BEFORE_AFK = config["guilds"][str(ctx.guild.id)]["COOPS_BEFORE_AFK"]

        for id in running_coops:
            if ctx.target_message.id == running_coops[id]["message_id"]:
                contract_id = id
        
        for coop in running_coops[contract_id]["coops"]:
            if not coop["completed_or_failed"]:
                await ctx.send(":warning: Some coops are still running", hidden=True)
                return

        # Deletes contract channel and category
        contract_channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
        await contract_channel.category.delete()
        await contract_channel.delete()
        
        # Updates running_coops JSON
        running_coops.pop(contract_id)
        self.utils.save_json("running_coops", running_coops)

        # Checks for new AFK
        archive = self.utils.read_json("participation_archive")
        date_dic = {}
        for coops in archive.values():
            for date, coop in coops.items():
                if date not in date_dic.keys():
                    date_dic[date] = []
                date_dic[date].append(coop)
        # Sorts by date
        date_dic = dict(sorted(date_dic.items(), reverse=True))
        # If members has not participated in last number of coops defined in COOPS_BEFORE_AFK (excluding already done leggacies), gives him AFK role
        # Alt accounts are not taken into account
        for member in ctx.guild.members:
            count = 0
            no_count = 0
            i = 0
            while count < COOPS_BEFORE_AFK and i < len(date_dic):
                key = list(date_dic.keys())[i]
                for coop in date_dic[key]:
                    if str(member.id) not in coop["participation"].keys():
                        continue
                    if coop["participation"][str(member.id)] in ["no", "afk"]:
                        no_count = no_count + 1
                    if coop["participation"][str(member.id)] != "leggacy":
                        count = count + 1
                i = i + 1
            if no_count >= COOPS_BEFORE_AFK:
                await member.add_roles(discord.utils.get(ctx.guild.roles, name="AFK"))    
    
    @cog_ext.cog_context_menu(name="Coop completed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), is_coop_creator_context_menu())
    async def coop_completed(self, ctx: MenuContext):
        
        running_coops = self.utils.read_json("running_coops")

        def get_contractid_coopnb():
            for contract_id in running_coops:
                for i in range(len(running_coops[contract_id]["coops"])):
                    if ctx.target_message.id == running_coops[contract_id]["coops"][i]["message_id"]:
                        return (contract_id, i+1)
        contract_id, coop_nb = get_contractid_coopnb()

        coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
        if (self.bot.owner_id != ctx.author.id
                and not ctx.author.guild_permissions.administrator
                and coop_role not in ctx.author.roles
                and running_coops[contract_id]["coops"][coop_nb-1]["creator"] != ctx.author.id):
            await ctx.send(":warning: You are not the creator of this coop", hidden=True)
            return
        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", hidden=True)
            return

        # Updates running_coops JSON
        running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"] = True
        self.utils.save_json("running_coops", running_coops)

        # Deletes coop role and coop channel
        await discord.utils.get(ctx.guild.roles, name=f"{contract_id}-{coop_nb}").delete()

        for channel in discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"]).category.text_channels:
            if channel.name == f"coop-{coop_nb}":
                await channel.delete()
                break

        # Updates coop message
        action_row = [create_actionrow(create_button(style=ButtonStyle.blurple,
                                                        label="COMPLETED",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                        disabled=True
                                                        ))]
        await ctx.target_message.edit(embed=ctx.target_message.embeds[0], components=action_row)

        # Removes coop creator role
        creator = ctx.guild.get_member(running_coops[contract_id]["coops"][coop_nb-1]["creator"])
        # If creator has not left the guild
        if creator != None:
            await creator.remove_roles(discord.utils.get(ctx.guild.roles, name="Coop Creator"))

        # Responds to the interaction
        await ctx.send(f"Marked the coop as completed :white_check_mark:", hidden=True)

    @cog_ext.cog_context_menu(name="Coop failed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_role("Coop Organizer"), is_coop_creator_context_menu())
    async def coop_failed(self, ctx: MenuContext):
        
        running_coops = self.utils.read_json("running_coops")

        def get_contractid_coopnb():
            for contract_id in running_coops:
                for i in range(len(running_coops[contract_id]["coops"])):
                    if ctx.target_message.id == running_coops[contract_id]["coops"][i]["message_id"]:
                        return (contract_id, i+1)
        contract_id, coop_nb = get_contractid_coopnb()

        coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
        if (self.bot.owner_id != ctx.author.id
                and not ctx.author.guild_permissions.administrator
                and coop_role not in ctx.author.roles
                and running_coops[contract_id]["coops"][coop_nb-1]["creator"] != ctx.author.id):
            await ctx.send(":warning: You are not the creator of this coop", hidden=True)
            return
        if running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"]:
            await ctx.send(":warning: Coop is already completed or failed", hidden=True)
            return

        # Removes coop creator role
        creator = ctx.guild.get_member(running_coops[contract_id]["coops"][coop_nb-1]["creator"])
        # If creator has not left the guild
        if creator != None:
            await creator.remove_roles(discord.utils.get(ctx.guild.roles, name="Coop Creator"))

        # Updates running_coops and archive JSONs
        archive = self.utils.read_json("participation_archive")

        running_coops[contract_id]["coops"][coop_nb-1]["completed_or_failed"] = True
        running_coops[contract_id]["coops"][coop_nb-1]["creator"] = ""

        for member_id in running_coops[contract_id]["coops"][coop_nb-1]["members"]:
            running_coops[contract_id]["remaining"].append(member_id)
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member_id)] = "no"
        running_coops[contract_id]["coops"][coop_nb-1]["members"] = []

        self.utils.save_json("running_coops", running_coops)
        self.utils.save_json("participation_archive", archive)

        # Deletes coop role and coop channel
        await discord.utils.get(ctx.guild.roles, name=f"{contract_id}-{coop_nb}").delete()

        for channel in discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"]).category.text_channels:
            if channel.name == f"coop-{coop_nb}":
                await channel.delete()
                break

        # Updates coop message
        coop_embed = ctx.target_message.embeds[0]
        coop_embed.title = f"Coop {coop_nb}"
        coop_embed.description = ""
        action_row = [create_actionrow(create_button(style=ButtonStyle.red,
                                                        label="FAILED",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                        disabled=True
                                                        ))]
        await ctx.target_message.edit(embed=coop_embed, components=action_row)

        # Updates contract message
        contract_message = await ctx.target_message.channel.fetch_message(running_coops[contract_id]["message_id"])

        remaining_mentions = []
        for id in running_coops[contract_id]["remaining"]:
            remaining_mentions.append(await self.utils.get_member_mention(id, ctx.guild, self.bot))
        
        remaining_index = contract_message.content.index("**Remaining:")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})** {''.join(remaining_mentions)}\n"
        await contract_message.edit(content=new_contract_content)

        # Responds to the interaction
        await ctx.send(f"Marked the coop as failed :white_check_mark:", hidden=True)


    ##################
    ##### Events #####
    ##################

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
                                                    custom_id="main"
                                                ),
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(ctx.author.id)]['alt']}",
                                                    custom_id="alt"
                                                )
                                            )
                await ctx.send("Which account is joining ?", components=[action_row], hidden=True)

                ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row)
                if ctx_alt.custom_id == "alt":
                    author_id = "alt" + str(ctx.author.id)
                    is_alt = True
                ctx_send = ctx_alt
            else:
                ctx_send = ctx

            # General checks
            running_coops = utils.read_json("running_coops")
            if "already_done" in running_coops[contract_id].keys() and author_id in running_coops[contract_id]["already_done"]:
                await ctx_send.send("You have already completed this contract :smile:", hidden=True)
                return
            for coop in running_coops[contract_id]["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", hidden=True)
                    return
            
            # If AFK and joins a coop, removes AFK role
            if author_id not in running_coops[contract_id]["remaining"]:
                afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
                if not is_alt and afk_role in ctx.author.roles: # Alt doesn't count for AFK
                    await ctx.author.remove_roles(afk_role)
            # Updates running_coops JSON
            else:
                running_coops[contract_id]["remaining"].remove(author_id)
            running_coops[contract_id]["coops"][coop_nb-1]["members"].append(author_id)
            utils.save_json("running_coops", running_coops)

            # Notif to coop organizers
            if len(running_coops[contract_id]["remaining"]) == 0:
                await self.send_notif_no_remaining(ctx.guild, contract_id)

            # Updates archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(author_id)] = "yes"
            utils.save_json("participation_archive", archive)

            # Updates contract message
            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(await utils.get_member_mention(id, ctx.guild, self.bot))
                
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            contract_message = await channel.fetch_message(running_coops[contract_id]["message_id"])
            remaining_index = contract_message.content.index("**Remaining:")
            new_contract_content = contract_message.content[:remaining_index] + f"**Remaining: ({len(remaining_mentions)})** {''.join(remaining_mentions)}\n"
            await contract_message.edit(content=new_contract_content)

            # Updates coop message
            coop_dic = running_coops[contract_id]["coops"][coop_nb-1]
            member_count = len(coop_dic["members"])
            if member_count == running_coops[contract_id]['size']:
                full = True
            else:
                full = False
            coop_dic["members"].remove(coop_dic["creator"])

            coop_embed = ctx.origin_message.embeds[0]
            coop_embed.title = f"Coop {coop_nb} - {member_count}/{running_coops[contract_id]['size']}{' FULL' if full else ''}"
            desc = f"**Members:**\n- {ctx.guild.get_member(coop_dic['creator']).mention} (Creator)\n"
            for member_id in coop_dic["members"]:
                desc = desc + f"- {await utils.get_member_mention(member_id, ctx.guild, self.bot)}\n"
            coop_embed.description = desc

            action_row = [create_actionrow(create_button(style=ButtonStyle.green,
                                                        label="Join",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                        disabled=full
                                                        ))]
            await ctx.origin_message.edit(embed=coop_embed, components=action_row)

            # Gives coop role for access to coop channel
            await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name=f"{contract_id}-{coop_nb}"))

            # Sends coop code in hidden message
            await ctx_send.send(f"Code to join **Coop {coop_nb}** of contract **{contract_id}** is: `{coop_dic['code']}`\n" +
                                "Don't forget to activate your deflector and ship in bottle :wink:", hidden=True)
        
        # Already done leggacy button
        elif ctx.custom_id.startswith("leggacy_"):
            contract_id = ctx.custom_id.split('_')[1]

            author_id = ctx.author.id

            # Check for alt
            alt_dic = utils.read_json("alt_index")
            alt_role = discord.utils.get(ctx.guild.roles, name="Alt")
            if alt_role in ctx.author.roles:
                action_row = create_actionrow(
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(ctx.author.id)]['main']}",
                                                    custom_id="main"
                                                ),
                                                create_button(style=ButtonStyle.grey,
                                                    label=f"{alt_dic[str(ctx.author.id)]['alt']}",
                                                    custom_id="alt"
                                                )
                                            )
                await ctx.send("Which account has already done the contract ?", components=[action_row], hidden=True)

                ctx_alt: ComponentContext = await wait_for_component(self.bot, components=action_row)
                if ctx_alt.custom_id == "alt":
                    author_id = "alt" + str(ctx.author.id)
                ctx_send = ctx_alt
            else:
                ctx_send = ctx

            running_coops = utils.read_json("running_coops")
            if author_id in running_coops[contract_id]["already_done"]:
                await ctx_send.send("You already told me that :smile:", hidden=True)
                return
            for coop in running_coops[contract_id]["coops"]:
                if author_id in coop["members"]:
                    await ctx_send.send("You have already joined a coop for this contract :smile:", hidden=True)
                    return
            
            # Updates running_coops JSON
            if author_id in running_coops[contract_id]["remaining"]:
                running_coops[contract_id]["remaining"].remove(author_id)
            running_coops[contract_id]["already_done"].append(author_id)
            utils.save_json("running_coops", running_coops)

            # Notif to coop organizers
            if len(running_coops[contract_id]["remaining"]) == 0:
                await self.send_notif_no_remaining(ctx.guild, contract_id)

            # Updates archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(author_id)] = "leggacy"
            utils.save_json("participation_archive", archive)

            # Updates contract message
            already_done_mentions = []
            for id in running_coops[contract_id]["already_done"]:
                already_done_mentions.append(await utils.get_member_mention(id, ctx.guild, self.bot))
            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(await utils.get_member_mention(id, ctx.guild, self.bot))
            
            content = ctx.origin_message.content
            index = content.index("**Already done:**")
            new_content = (content[:index]
                            + f"**Already done:** {''.join(already_done_mentions)}\n\n"
                            + f"**Remaining: ({len(remaining_mentions)})** {''.join(remaining_mentions)}\n"
                            )
            await ctx.origin_message.edit(content=new_content)

            # Responds to the interaction
            await ctx_send.send(f"Marked you as already done :white_check_mark:", hidden=True)


    ########################
    ##### Misc methods #####
    ########################

    async def send_notif_no_remaining(self, guild, contract_id):
        orga_role = discord.utils.get(guild.roles, name="Coop Organizer")

        running_coops = self.utils.read_json("running_coops")
        contract_channel = discord.utils.get(guild.channels, id=running_coops[contract_id]["channel_id"])
        
        await contract_channel.send(f"{orga_role.mention} Everyone has joined a coop for this contract :tada:")

def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog("Coop")
