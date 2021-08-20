import discord
from discord.ext import commands


class Coop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog("Utils")


def setup(bot):
    bot.add_cog(Coop(bot))

def teardown(bot):
    bot.remove_cog('Coop')