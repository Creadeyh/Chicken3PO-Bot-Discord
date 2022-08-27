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
        "COOPS_BEFORE_AFK": 3,
        "GUEST_ROLE_ID": "",
        "KEEP_COOP_CHANNELS": False,
        "USE_EMBEDS": True
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

@bot.command(name="getdatafile")
@commands.is_owner()
async def get_data_file(ctx, filename):

    dm_channel = ctx.author.dm_channel
    if dm_channel == None:
        await ctx.author.create_dm()
        dm_channel = ctx.author.dm_channel
    
    try:
        with open(f"data/{filename}.json", "rb") as f:
            await dm_channel.send(file=discord.File(f))
    except Exception as inst:
        await ctx.send(f"Administrative error (#3) :confounded:\n```{type(inst)}\n{inst}```")
        return

@bot.command(name="modifydatafile")
@commands.is_owner()
async def modify_data_file(ctx, filename, key_path, value = None):

    try:
        file = utils.read_json(filename)

        data = file
        keys = key_path.split("/")
        i = 1
        while i < len(keys):
            if keys[i-1].isnumeric():
                data = data[int(keys[i-1])]
            else:
                data = data[keys[i-1]]
            i += 1
        
        if value == None:
            if type(data) == list:
                data.pop(keys[-1])
            else:
                raise Exception
        elif value.isnumeric():
            data[keys[-1]] = int(value)
        elif value.lower() == "true":
            data[keys[-1]] = True
        elif value.lower() == "false":
            data[keys[-1]] = False
        else:
            data[keys[-1]] = value
        
        utils.save_json(filename, file)
    except Exception as inst:
        await ctx.send(f"Administrative error (#4) :confounded:\n```{type(inst)}\n{inst}```")
        return

@bot.command(name="update-data-version")
@commands.is_owner()
async def update_data_version(ctx):
    with open("config.json", "r") as f:
        config = json.load(f)

    # Pre 1.3.7
    if "BOT_VERSION" not in config.keys():

        # Added database connection
        config["DB_HOSTNAME"] = "localhost"
        config["DB_PORT"] = 27017
        config["DB_NAME"] = "test_database"

        # Added version for update checks
        config["BOT_VERSION"] = "1.3.7"
        
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        await ctx.send("Successfully updated data to 1.3.7 :white_check_mark:", hidden=True)

    elif config["BOT_VERSION"] == "1.3.7":
        config.pop("DB_HOSTNAME")
        config.pop("DB_PORT")
        config["DB_STRING"] = "mongodb://localhost:27017"
        config["BOT_VERSION"] = "1.3.7.1"

        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        await ctx.send("Successfully updated data to 1.3.7.1 :white_check_mark:", hidden=True)


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

    role_error = False
    bot_role = discord.utils.get(ctx.guild.roles, name=bot.user.name)
    if not bot_role:
        await ctx.send("ERROR: Bot role not found")
        return
    
    if coop_role and coop_role.position > bot_role.position:
        role_error = True
        await ctx.send("Please move the Coop Organizer below the bot role")
    elif not coop_role:
        coop_role = await ctx.guild.create_role(name="Coop Organizer", mentionable=True)
        await ctx.send("Coop Organizer role created")
    if creator_role and creator_role.position > bot_role.position:
        role_error = True
        await ctx.send("Please move the Coop Creator below the bot role")
    elif not creator_role:
        creator_role = await ctx.guild.create_role(name="Coop Creator")
        await ctx.send("Coop Creator role created")
    if afk_role and afk_role.position > bot_role.position:
        role_error = True
        await ctx.send("Please move the AFK below the bot role")
    elif not afk_role:
        afk_role = await ctx.guild.create_role(name="AFK")
        await ctx.send("AFK role created")
    if alt_role and alt_role.position > bot_role.position:
        role_error = True
        await ctx.send("Please move the Alt below the bot role")
    elif not alt_role:
        alt_role = await ctx.guild.create_role(name="Alt")
        await ctx.send("Alt role created")

    if role_error:
        await ctx.send("Bot setup incomplete, please make changes and retry :x:")
    else:
        await ctx.send("Bot setup done :white_check_mark:")

bot.remove_command("help")


bot.run(TOKEN)
