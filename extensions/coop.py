import discord
from discord.ext import commands

from discord_slash import cog_ext
from discord_slash.context import *
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import *
from discord_slash.model import *

import json

with open('config.json', 'r') as f:
    config = json.load(f)
    #GUILD_ID = config["GUILD_ID"]
    # TODO temp
    GUILD_ID = 643427894504325126

class Coop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog("Utils")

    def is_coop_creator():
        """
        For check_any decorator
        """
        def predicate(ctx):
            # TODO ctx.bot
            return ctx.author.id == ""
        return commands.check(predicate)

    ##### Slash Commands #####
    
    @cog_ext.cog_slash(name="contract", guild_ids=[GUILD_ID])
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def add_contract(self, ctx: SlashContext):
        # TODO
        # add leggacy button if leggacy
        print()
    
    @cog_ext.cog_slash(name="coop", guild_ids=[GUILD_ID])
    async def add_coop(self, ctx: SlashContext):
        # TODO
        # add join button
        print()

    @cog_ext.cog_slash(name="kick", guild_ids=[GUILD_ID])
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator())
    async def kick_from_coop(self, ctx: SlashContext):
        # TODO
        print()
    
    @cog_ext.cog_slash(name="codes", guild_ids=[GUILD_ID])
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def get_coop_codes(self, ctx: SlashContext):
        # TODO
        print()


    ##### Context Menus #####

    @cog_ext.cog_context_menu(name="Remove contract",
                            guild_ids=[GUILD_ID],
                            target=ContextMenuType.MESSAGE)
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
    async def remove_contract(ctx: MenuContext):
        # TODO
        print()
    
    @cog_ext.cog_context_menu(name="Coop completed",
                            guild_ids=[GUILD_ID],
                            target=ContextMenuType.MESSAGE)
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator())
    async def coop_completed(ctx: MenuContext):
        # TODO
        print()

    @cog_ext.cog_context_menu(name="Coop failed",
                            guild_ids=[GUILD_ID],
                            target=ContextMenuType.MESSAGE)
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), is_coop_creator())
    async def coop_failed(ctx: MenuContext):
        # TODO
        print()


    ##### Events #####

    @commands.Cog.listener()
    async def on_component(ctx: ComponentContext):
        # TODO
        # buttons leggacy or join
        print()


def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog('Coop')