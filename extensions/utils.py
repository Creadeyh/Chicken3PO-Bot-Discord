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
    
    @staticmethod
    def get_bot_channel_id(guild_id):
        with open("config.json", "r") as f:
            config = json.load(f)
        return config["guilds"][str(guild_id)]["BOT_CHANNEL_ID"]

    @staticmethod
    def get_member_mention(member_id, guild):
        if str(member_id).startswith("alt"):
            alt_dic = Utils.read_json("alt_index")
            main_id = member_id.replace("alt", "")
            return guild.get_member(int(main_id)).mention + f"({alt_dic[main_id]['alt']})"
        elif discord.utils.get(guild.roles, name="Alt") in guild.get_member(member_id).roles:
            alt_dic = Utils.read_json("alt_index")
            return guild.get_member(member_id).mention + f"({alt_dic[str(member_id)]['main']})"
        else:
            return guild.get_member(member_id).mention

def setup(bot):
    bot.add_cog(Utils(bot))

def teardown(bot):
    bot.remove_cog("Utils")
