import discord
from discord.ext import commands


class Coop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog('Coop')