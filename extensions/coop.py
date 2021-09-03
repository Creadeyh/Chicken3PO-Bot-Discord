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

    def is_coop_creator_slash_command():
        """
        Checks if command author is creator of at least one of the running coops
        """
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops.values():
                for coop in contract["coops"]:
                    if ctx.author.id == coop["creator"]:
                        return True
            return False
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
                        description="Registers a new contract",
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
                                description="If the contract is a leggacy or not",
                                option_type=SlashCommandOptionType.BOOLEAN,
                                required=True
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
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
        channel = await category.create_text_channel(contract_id,
                                                    overwrites={
                                                        ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False,
                                                                                                            add_reactions=False
                                                                                                            ),
                                                        discord.utils.get(ctx.guild.roles, name="Chicken3PO"): discord.PermissionOverwrite(send_messages=True)
                                                    })
        
        # Gets people without the AFK role and who haven't done the contract already (according to bot archive)
        def member_in_previous_coop(member_id):
            for contract in archive[contract_id].values():
                if str(member_id) in contract["participation"].keys() and contract["participation"][str(member_id)] in ["yes", "leggacy"]:
                    return True
            return False
        
        afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
        remaining = []
        already_done = []
        for member in ctx.guild.members:
            if not member.bot and afk_role not in member.roles:
                if is_leggacy and member_in_previous_coop(member.id):
                    already_done.append(member)
                else:
                    remaining.append(member)
        
        # Sends the contract message
        contract_string = ("==============================\n"
                        + f"**{'LEGGACY ' if is_leggacy else ''}Contract available**\n"
                        + f"*Contract ID:* `{contract_id}`\n"
                        + f"*Coop size:* {size}\n"
                        + "==============================\n\n"
                        + (f"**Already done:** {''.join([member.mention for member in already_done])}\n\n" if is_leggacy else "")
                        + f"**Remaining:** {''.join([member.mention for member in remaining])}\n"
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
            "remaining": [member.id for member in remaining]
        }
        if is_leggacy:
            dic_contract["already_done"] = []
        
        running_coops[contract_id] = dic_contract
        self.utils.save_json("running_coops", running_coops)

        # Creates the contract in archive JSON
        if not contract_id in archive.keys():
            archive[contract_id] = {}
        
        participation = {}
        for member in remaining:
            participation[str(member.id)] = "no"
        
        archive[contract_id][contract_date] = {
            "is_leggacy": is_leggacy,
            "participation": participation
        }
        self.utils.save_json("participation_archive", archive)

        # Responds to the interaction
        await ctx.send("Contract registered :white_check_mark:", hidden=True)
    
    @cog_ext.cog_slash(name="coop",
                        description="Registers a new coop",
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

        # Updates running_coops JSON
        coop_dic = {
            "code": coop_code,
            "creator": ctx.author.id,
            "message_id": message.id,
            "locked": locked,
            "members": [ctx.author.id]
        }
        running_coops[contract_id]["coops"].append(coop_dic)
        running_coops[contract_id]["remaining"].remove(ctx.author.id)
        self.utils.save_json("running_coops", running_coops)

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
            remaining_mentions.append(ctx.guild.get_member(id).mention)
        
        contract_message = await contract_channel.fetch_message(running_coops[contract_id]["message_id"])
        remaining_index = contract_message.content.index("**Remaining:**")
        new_contract_content = contract_message.content[:remaining_index] + f"**Remaining:** {''.join(remaining_mentions)}\n"
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
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_slash_command())
    async def lock_coop(self, ctx: SlashContext, contract_id: str, coop_nb: int=None):

        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx.send(":warning: Invalid coop number", hidden=True)
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
            if (is_author_creator and creator_coop_nb == coop_nb) or self.bot.owner_id == ctx.author.id or ctx.author.guild_permissions.administrator:
                await lock(coop_nb)
            else:
                await ctx.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
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
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_slash_command())
    async def unlock_coop(self, ctx: SlashContext, contract_id: str, coop_nb: int=None):

        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx.send(":warning: Invalid coop number", hidden=True)
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
            if (is_author_creator and creator_coop_nb == coop_nb) or self.bot.owner_id == ctx.author.id or ctx.author.guild_permissions.administrator:
                await unlock(coop_nb)
            else:
                await ctx.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
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
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_slash_command())
    async def kick_from_coop(self, ctx: SlashContext, member: discord.Member, contract_id: str, coop_nb: int=None):
        # TODO checks when kick yourself or last member of coop
        running_coops = self.utils.read_json("running_coops")
        if contract_id not in running_coops.keys():
            await ctx.send(":warning: Contract does not exist", hidden=True)
            return
        if (member.id in running_coops[contract_id]["remaining"]
            or ("already_done" in running_coops[contract_id].keys() and member.id in running_coops[contract_id]["already_done"])):
            await ctx.send(":warning: Member is not in a coop for this contract", hidden=True)
            return
        if coop_nb != None:
            if coop_nb <= 0 or coop_nb > len(running_coops[contract_id]["coops"]):
                await ctx.send(":warning: Invalid coop number", hidden=True)
                return
            if member.id not in running_coops[contract_id]["coops"][coop_nb-1]["members"]:
                await ctx.send(":warning: Member is not in this coop", hidden=True)
                return

        is_author_creator = False
        for i in range(len(running_coops[contract_id]["coops"])):
            if running_coops[contract_id]["coops"][i]["creator"] == ctx.author.id:
                is_author_creator = True
                creator_coop_nb = i + 1

        async def kick(from_coop_nb):
            # Updates running_coops JSON
            running_coops[contract_id]["coops"][from_coop_nb-1]["members"].remove(member.id)
            running_coops[contract_id]["remaining"].append(member.id)
            self.utils.save_json("running_coops", running_coops)

            # Updates coop message
            coop_dic = running_coops[contract_id]["coops"][from_coop_nb-1]
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            coop_message = await channel.fetch_message(coop_dic["message_id"])
            
            coop_embed = coop_message.embeds[0]
            coop_embed.title = f"Coop {from_coop_nb} - {len(coop_dic['members'])}/{running_coops[contract_id]['size']}"
            desc = f"**Members:**\n- {ctx.guild.get_member(coop_dic['creator']).mention} (Creator)\n"
            for member_id in coop_dic["members"]:
                if member_id == coop_dic["creator"]:
                    continue
                desc = desc + f"- {ctx.guild.get_member(member_id).mention}\n"
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
                remaining_mentions.append(ctx.guild.get_member(id).mention)
            
            remaining_index = contract_message.content.index("**Remaining:**")
            new_contract_content = contract_message.content[:remaining_index] + f"**Remaining:** {''.join(remaining_mentions)}\n"
            await contract_message.edit(content=new_contract_content)

            # Updates archive JSON
            archive = self.utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member.id)] = "no"
            self.utils.save_json("participation_archive", archive)
        
        if coop_nb != None:
            if (is_author_creator and creator_coop_nb == coop_nb) or self.bot.owner_id == ctx.author.id or ctx.author.guild_permissions.administrator:
                await kick(coop_nb)
            else:
                await ctx.send(f":warning: You are not the creator of **Coop {coop_nb}** of contract `{contract_id}`", hidden=True)
                return
        else:
            if is_author_creator:
                if member.id in running_coops[contract_id]["coops"][creator_coop_nb-1]["members"]:
                    await kick(creator_coop_nb)
                else:
                    await ctx.send(f":warning: Member is not in the coop you created (Coop {creator_coop_nb})", hidden=True)
                    return
            else:
                await ctx.send(f":warning: You are not creator of any coop for contract `{contract_id}`", hidden=True)
                return
        
        # Responds to the interaction
        await ctx.send(f"{member.mention} kicked from coop", hidden=True)
    
    @cog_ext.cog_slash(name="codes",
                        description="Sends in DM the codes of currently running coops",
                        guild_ids=GUILD_IDS,
                        options=[
                            create_option(
                                name="contract_id",
                                description="The contract for which you want the coop codes. If not given, sends for all contracts",
                                option_type=SlashCommandOptionType.STRING,
                                required=False
                            )
                        ])
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
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


    #########################
    ##### Context Menus #####
    #########################

    @cog_ext.cog_context_menu(name="Remove contract",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_contract()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def remove_contract(self, ctx: MenuContext):
        # TODO
        print()
    
    @cog_ext.cog_context_menu(name="Coop completed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_context_menu())
        # TODO
        print()
    async def coop_completed(self, ctx: MenuContext):

    @cog_ext.cog_context_menu(name="Coop failed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_context_menu())
    async def coop_failed(self, ctx: MenuContext):
        # TODO
        print()


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

            running_coops = utils.read_json("running_coops")
            member = ctx.author
            if "already_done" in running_coops[contract_id].keys() and member.id in running_coops[contract_id]["already_done"]:
                await ctx.send("You have already completed this contract :smile:", hidden=True)
                return
            for coop in running_coops[contract_id]["coops"]:
                if member.id in coop["members"]:
                    await ctx.send("You have already joined a coop for this contract :smile:", hidden=True)
                    return
            
            # Updates running_coops JSON
            running_coops[contract_id]["remaining"].remove(member.id)
            running_coops[contract_id]["coops"][coop_nb-1]["members"].append(member.id)
            utils.save_json("running_coops", running_coops)

            # Notif to coop organizers
            if len(running_coops[contract_id]["remaining"]) == 0:
                await self.send_notif_no_remaining(ctx.guild, contract_id)

            # Updates archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member.id)] = "yes"
            utils.save_json("participation_archive", archive)

            # Updates contract message
            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(ctx.guild.get_member(id).mention)
                
            channel = discord.utils.get(ctx.guild.channels, id=running_coops[contract_id]["channel_id"])
            contract_message = await channel.fetch_message(running_coops[contract_id]["message_id"])
            remaining_index = contract_message.content.index("**Remaining:**")
            new_contract_content = contract_message.content[:remaining_index] + f"**Remaining:** {''.join(remaining_mentions)}\n"
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
                desc = desc + f"- {ctx.guild.get_member(member_id).mention}\n"
            coop_embed.description = desc

            action_row = [create_actionrow(create_button(style=ButtonStyle.green,
                                                        label="Join",
                                                        custom_id=f"joincoop_{contract_id}_{coop_nb}",
                                                        disabled=full
                                                        ))]
            await ctx.edit_origin(embed=coop_embed, components=action_row)

            # Sends coop code in hidden message
            await ctx.send(f"Code to join **Coop {coop_nb}** of contract **{contract_id}** is: `{coop_dic['code']}`\n" +
                            "Don't forget to activate your deflector and ship in bottle :wink:", hidden=True)
        
        # Already done leggacy button
        elif ctx.custom_id.startswith("leggacy_"):
            contract_id = ctx.custom_id.split('_')[1]

            running_coops = utils.read_json("running_coops")
            member = ctx.author
            if member.id in running_coops[contract_id]["already_done"]:
                await ctx.send("You already told me that :smile:", hidden=True)
                return
            for coop in running_coops[contract_id]["coops"]:
                if member.id in coop["members"]:
                    await ctx.send("You have already joined a coop for this contract :smile:", hidden=True)
                    return
            
            # Updates running_coops JSON
            if member.id in running_coops[contract_id]["remaining"]:
                running_coops[contract_id]["remaining"].remove(member.id)
            running_coops[contract_id]["already_done"].append(member.id)
            utils.save_json("running_coops", running_coops)

            # Notif to coop organizers
            if len(running_coops[contract_id]["remaining"]) == 0:
                await self.send_notif_no_remaining(ctx.guild, contract_id)

            # Updates archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member.id)] = "leggacy"
            utils.save_json("participation_archive", archive)

            # Updates contract message
            already_done_mentions = []
            for id in running_coops[contract_id]["already_done"]:
                already_done_mentions.append(ctx.guild.get_member(id).mention)
            remaining_mentions = []
            for id in running_coops[contract_id]["remaining"]:
                remaining_mentions.append(ctx.guild.get_member(id).mention)
            
            content = ctx.origin_message.content
            index = content.index("**Already done:**")
            new_content = (content[:index]
                            + f"**Already done:** {''.join(already_done_mentions)}\n\n"
                            + f"**Remaining:** {''.join(remaining_mentions)}\n"
                            )
            await ctx.edit_origin(content=new_content)


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
