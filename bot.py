import discord
from discord.ext import commands
from discord_slash import SlashCommand
from discord_slash.context import *

import json


##### Inits #####

intents = discord.Intents.default()
intents.members = True

with open('config.json', 'r') as f:
    config = json.load(f)
    TOKEN = config['TOKEN']
    COMMAND_PREFIX = config['COMMAND_PREFIX']
    CHANNEL_ID = config["CHANNEL_ID"]

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

bot.load_extension("extensions.coop")
bot.load_extension("extensions.utils")
coop = bot.get_cog("Coop")
utils = bot.get_cog("Utils")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game('Egg Inc with Wall-Egg | &help'))
    # await bot.change_presence(activity=discord.Game("DON'T USE I'M TESTING"))
    print("Bot is ready")


##### Owner commands #####

@bot.command(name="reloadext")
@commands.is_owner()
async def reload_extensions(ctx):
    try:
        bot.reload_extension("extensions.coop")
        bot.reload_extension("extensions.utils")
        await slash.sync_all_commands()
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


##### Events #####

# TODO change ?
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Something is missing from this command :thinking:")
    else:
        print(error)

@bot.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, commands.CheckAnyFailure):
        await ctx.send("Unauthorized command :no_entry_sign:", hidden=True)


##### Base Commands #####

@bot.command()
@commands.is_owner()
async def test(ctx):
    print()

@slash.slash(name="setuphere")
@commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
async def setuphere(ctx: SlashContext):
    """
    Bot init within the server
    """
    # TODO
    print()

bot.remove_command('help')

@bot.command()
async def help(ctx):
    dm_channel = ctx.author.dm_channel
    if dm_channel == None:
        await ctx.author.create_dm()
        dm_channel = ctx.author.dm_channel

    await ctx.send("Sending you help in your DMs :ambulance:")

    # TODO
    await dm_channel.send("bilbius bad")


bot.run(TOKEN)
