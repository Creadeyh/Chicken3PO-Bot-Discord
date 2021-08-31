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

    def is_coop_creator_context_menu():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops:
                for coop in contract["coops"]:
                    if ctx.target_message.id == coop["message_id"] and ctx.author.id == coop["creator"]:
                        return True
            return False
        return commands.check(predicate)
    
    def check_context_menu_target_contract():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops:
                if ctx.target_message.id == contract["message_id"]:
                    return True
            return False
        return commands.check(predicate)

    def check_context_menu_target_coop():
        def predicate(ctx):
            running_coops = ctx.bot.get_cog("Utils").read_json("running_coops")
            for contract in running_coops:
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
                            )
                        ])
    @is_bot_channel()
    async def add_coop(self, ctx: SlashContext, contract_id: str, coop_code: str):
        
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
        action_row = [create_actionrow(create_button(style=ButtonStyle.green, label="Join", custom_id=f"joincoop_{contract_id}_{coop_nb}"))]
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

    @cog_ext.cog_slash(name="kick", guild_ids=GUILD_IDS)
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))# TODO, is_coop_creator())
    async def kick_from_coop(self, ctx: SlashContext):
        # TODO
        print()
    
    @cog_ext.cog_slash(name="codes", guild_ids=GUILD_IDS)
    @is_bot_channel()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def get_coop_codes(self, ctx: SlashContext):
        # TODO
        print()


    #########################
    ##### Context Menus #####
    #########################

    @cog_ext.cog_context_menu(name="Remove contract",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_contract()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def remove_contract(ctx: MenuContext):
        # TODO
        print()
    
    @cog_ext.cog_context_menu(name="Coop completed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_context_menu())
    async def coop_completed(ctx: MenuContext):
        # TODO
        print()

    @cog_ext.cog_context_menu(name="Coop failed",
                            guild_ids=GUILD_IDS,
                            target=ContextMenuType.MESSAGE)
    @check_context_menu_target_coop()
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator_context_menu())
    async def coop_failed(ctx: MenuContext):
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
            coop_message = await channel.fetch_message(coop_dic["message_id"])

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
        for member in orga_role.members:
            await member.dm_channel.send(f"Everyone has joined a coop for the contract `{contract_id}` :tada:")

def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog("Coop")
