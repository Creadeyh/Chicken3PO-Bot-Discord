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
        if contract_id in running_coops.keys():
            await ctx.send(":warning: Contract already exists", hidden=True)
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
        
        # TODO if leggacy, check if player has participated in original contract in archive
        # Gets mentions and ids of people without the AFK role
        afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
        remaining_ids = []
        remaining_mentions = []
        for member in ctx.guild.members:
            if not member.bot and afk_role not in member.roles:
                remaining_ids.append(member.id)
                remaining_mentions.append(member.mention)
        
        # Sends the contract message
        contract_string = ("============================================================\n"
                        + f"**{'LEGGACY ' if is_leggacy else ''}Contract available**\n"
                        + f"*Contract ID:* `{contract_id}`\n"
                        + f"*Coop size:* {size}\n"
                        + "============================================================\n\n"
                        + ("**Already done:**\n\n" if is_leggacy else "")
                        + f"**Remaining:** {''.join(remaining_mentions)}\n"
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
            dic_contract["already_done"] = []
        
        running_coops[contract_id] = dic_contract
        self.utils.save_json("running_coops", running_coops)

        # Creates the contract in archive JSON
        archive = self.utils.read_json("participation_archive")
        if not contract_id in archive.keys():
            archive[contract_id] = {}
        
        participation = {}
        for id in remaining_ids:
            participation[str(id)] = "no"
        
        archive[contract_id][contract_date] = {
            "is_leggacy": is_leggacy,
            "participation": participation
        }
        self.utils.save_json("participation_archive", archive)
    
    @cog_ext.cog_slash(name="coop", guild_ids=GUILD_IDS)
    @is_bot_channel()
    async def add_coop(self, ctx: SlashContext):
        # TODO
        # add join button
        print()

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
        # TODO
        # button join coop
        utils = ctx.bot.get_cog("Utils")

        # Already done leggacy button
        if ctx.custom_id.startswith("leggacy_"):
            contract_id = ctx.custom_id.split('_')[1]

            # Update running_coops JSON
            running_coops = utils.read_json("running_coops")
            member = ctx.author
            if member.id in running_coops[contract_id]["already_done"]:
                await ctx.send("You already told me that :smile:", hidden=True)
                return
            running_coops[contract_id]["remaining"].remove(member.id)
            running_coops[contract_id]["already_done"].append(member.id)
            utils.save_json("running_coops", running_coops)

            # Update archive JSON
            archive = utils.read_json("participation_archive")
            archive[contract_id][ running_coops[contract_id]["date"] ]["participation"][str(member.id)] = "leggacy"
            utils.save_json("participation_archive", archive)

            # Update contract message
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


def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog("Coop")
