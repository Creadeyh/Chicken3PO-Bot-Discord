import discord
from discord.ext import commands
from discord_slash import SlashCommand
from discord_slash.context import *
from discord_slash.error import CheckFailure

import json


##### Inits #####

intents = discord.Intents.default()
intents.members = True

with open("config.json", "r") as f:
    config = json.load(f)
    TOKEN = config["TOKEN"]
    COMMAND_PREFIX = config["COMMAND_PREFIX"]

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

bot.load_extension("extensions.utils")
bot.load_extension("extensions.user_utils")
bot.load_extension("extensions.coop")
coop = bot.get_cog("Coop")
user_utils = bot.get_cog("UserUtils")
utils = bot.get_cog("Utils")


#######################
##### Main events #####
#######################

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Egg Inc with Wall-Egg | /help"))
    print("Bot is ready")

async def reload_extensions():
    bot.reload_extension("extensions.utils")
    bot.reload_extension("extensions.user_utils")
    bot.reload_extension("extensions.coop")

@bot.event
async def on_guild_join(guild):
    with open("config.json", "r") as f:
        config = json.load(f)
    config["guilds"][str(guild.id)] = {
        "BOT_CHANNEL_ID": "",
        "COOPS_BEFORE_AFK": 3
        }
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    await reload_extensions()

@bot.event
async def on_guild_remove(guild):
    with open("config.json", "r") as f:
        config = json.load(f)
    config["guilds"].pop(str(guild.id))
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    await reload_extensions()


##########################
##### Owner commands #####
##########################

@bot.command(name="reloadext")
@commands.is_owner()
async def reload_extensions_command(ctx):
    try:
        await reload_extensions()
    except Exception as inst:
        await ctx.send(f"Administrative error (#1) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send("All extensions have been reloaded :arrows_counterclockwise:")

@bot.command(name="serverlist")
@commands.is_owner()
async def get_server_list(ctx):

        dm_channel = ctx.author.dm_channel
        if dm_channel == None:
            await ctx.author.create_dm()
            dm_channel = ctx.author.dm_channel

        liste = {}
        for guild in bot.guilds:
            liste[guild.name] = guild.id
        await dm_channel.send(liste)

@bot.command(name="removeserver")
@commands.is_owner()
async def remove_from_server(ctx, id):
    try:
        guild = await bot.fetch_guild(id)
        await guild.leave()
    except Exception as inst:
        await ctx.send(f"Administrative error (#2) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send(f"Left {guild.name} :wink:")


##########################
##### Command events #####
##########################

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Something is missing from this command :thinking:")
    else:
        print(error)

@bot.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, CheckFailure):
        if any(substring in ctx.name for substring in ["Remove contract", "Coop completed", "Coop failed"]):
            await ctx.send("Unauthorized target message :no_entry_sign:", hidden=True)
        elif discord.utils.get(ctx.guild.roles, name="AFK") in ctx.author.roles:
            await ctx.send("Unauthorized command as AFK :no_entry_sign:", hidden=True)
        else:
            await ctx.send("Unauthorized channel for this command :no_entry_sign:", hidden=True)
    elif isinstance(error, commands.CheckAnyFailure):
        await ctx.send("Unauthorized command :no_entry_sign:", hidden=True)
    else:
        print(error)


#########################
##### Setup Command #####
#########################

@bot.command()
@commands.guild_only()
@commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
async def setuphere(ctx):
    """
    Bot init within the server
    """
    with open("config.json", "r") as f:
        config = json.load(f)
    config["guilds"][str(ctx.guild.id)]["BOT_CHANNEL_ID"] = ctx.channel.id
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    await ctx.send(f"Bot commands channel set as {ctx.channel.mention}")

    # Creates Coop Organizer, Coop Creator, AFK and Alt roles if not exist
    coop_role = discord.utils.get(ctx.guild.roles, name="Coop Organizer")
    creator_role = discord.utils.get(ctx.guild.roles, name="Coop Creator")
    afk_role = discord.utils.get(ctx.guild.roles, name="AFK")
    alt_role = discord.utils.get(ctx.guild.roles, name="Alt")

    if not coop_role:
        await ctx.guild.create_role(name="Coop Organizer", mentionable=True)
        await ctx.send("Coop Organizer role created")
    if not creator_role:
        await ctx.guild.create_role(name="Coop Creator")
        await ctx.send("Coop Creator role created")
    if not afk_role:
        await ctx.guild.create_role(name="AFK")
        await ctx.send("AFK role created")
    if not alt_role:
        await ctx.guild.create_role(name="Alt")
        await ctx.send("Alt role created")

    await ctx.send("Bot setup done :white_check_mark:")

bot.remove_command("help")


bot.run(TOKEN)
