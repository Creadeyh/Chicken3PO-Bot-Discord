import discord
from discord.ext import commands

import json

JSON_PATH = "data/"

class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def read_json(name):
        try:
            with open(f"{JSON_PATH}{name}.json", "r") as f:
                dic = json.load(f)
        except FileNotFoundError:
            dic = {}
            with open(f"{JSON_PATH}{name}.json", "w") as f:
                json.dump(dic, f, indent=4)
        return dic

    @staticmethod
    def save_json(name, dic):
        with open(f"{JSON_PATH}{name}.json", "w") as f:
            json.dump(dic, f, indent=4)

def setup(bot):
    bot.add_cog(Utils(bot))

def teardown(bot):
    bot.remove_cog('Utils')