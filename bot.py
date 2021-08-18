import discord
from discord.ext import commands

import os
import asyncio
import json

intents = discord.Intents.default()
intents.members = True

with open('config.json', 'r') as f:
    config = json.load(f)
    TOKEN = config['TOKEN']
    COMMAND_PREFIX = config['COMMAND_PREFIX']

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


##### Commands #####



##### Admin commands #####

def checkOwner(ctx):
    return ctx.author.id == 146263952085614592

@bot.command()
@commands.check(checkOwner)
async def reloadCogs(ctx):
    try:
        print()
        # for folder in os.listdir("./games"):
        #     for filename in os.listdir(f"./games/{folder}"):
        #         if filename.endswith(".py"):
        #             bot.unload_extension(f"games.{folder}.{filename[:-3]}")
        #             bot.load_extension(f"games.{folder}.{filename[:-3]}")
    except Exception as inst:
        await ctx.send(f"Seems like I encountered an error (*3) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send("All cogs have been reloaded :arrows_counterclockwise:")

@bot.command()
@commands.check(checkOwner)
async def getServerList(ctx):

        dmChannel = ctx.author.dm_channel
        if dmChannel == None:
            await ctx.author.create_dm()
            dmChannel = ctx.author.dm_channel

        liste = {}
        for guild in bot.guilds:
            liste[guild.name] = guild.id
        await dmChannel.send(liste)

@bot.command()
@commands.check(checkOwner)
async def removeFromServer(ctx, id):
    try:
        guild = await bot.fetch_guild(id)
        await guild.leave()
    except Exception as inst:
        await ctx.send(f"Administrative error (#1) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send(f"Left {guild.name} :wink:")

##### Events #####

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Something is missing from this command :thinking:")
    else:
        print(error)
        

##### Inits #####

bot.remove_command('help')

@bot.command()
async def help(ctx):
    dmChannel = ctx.author.dm_channel
    if dmChannel == None:
        await ctx.author.create_dm()
        dmChannel = ctx.author.dm_channel

    await ctx.send("Sending you help in your DMs :ambulance:")

    # TODO
    # embed = discord.Embed(title="Ur Bot Help", color=discord.Color.red(),
    #                     description="&help                      > This command\n" +
    #                                 "&games                     > Returns the list of available games\n" +
    #                                 "&rules [game] [@someone]   > Sends the rules for a given game. Optional person to send to. If none, sends to request author\n" +
    #                                 "&play [game] [@someone]    > Starts a game with someone")
    # await dmChannel.send(embed=embed)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game('Egg Inc with Wall-Egg | &help'))
    # await bot.change_presence(activity=discord.Game("DON'T USE I'M TESTING"))
    print("Bot is ready")

def initBot():
    """
    Loads other python files (cogs) into the bot
    """

    print("No cogs loaded...")
    # for folder in os.listdir("./games"):
    #     for filename in os.listdir(f"./games/{folder}"):
    #         if filename.endswith(".py"):
    #             bot.load_extension(f"games.{folder}.{filename[:-3]}")


initBot()
bot.run(TOKEN)
