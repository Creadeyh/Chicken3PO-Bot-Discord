import discord
from discord.ext import commands


class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Utils(bot))

def teardown(bot):
    bot.remove_cog('Utils')