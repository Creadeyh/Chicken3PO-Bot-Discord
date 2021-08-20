import discord
from discord.ext import commands

import json


class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def checkOwner(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @staticmethod
    async def readJSON(name):
        try:
            with open(f"data/{name}.json", "r") as f:
                dic = json.load(f)
        except FileNotFoundError:
            dic = {}
            with open(f"data/{name}.json", "w") as f:
                json.dump(dic, f, indent=4)
        return dic

    @staticmethod
    async def saveJSON(name, dic):
        with open(f"data/{name}.json", "w") as f:
            json.dump(dic, f, indent=4)

def setup(bot):
    bot.add_cog(Utils(bot))

def teardown(bot):
    bot.remove_cog('Utils')