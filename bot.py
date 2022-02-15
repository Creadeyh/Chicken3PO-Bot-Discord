import discord as dpy
from discord.ext import commands as dpy_commands
import interactions

import extensions.utils as utils

import json
import asyncio

#region Inits

dpy_intents = dpy.Intents.default()
dpy_intents.members = True
intents = interactions.Intents.DEFAULT | interactions.Intents.GUILD_MEMBERS
# act_list = []
# act_list.append(interactions.PresenceActivity(name="Message", details="Egg Inc with Wall-Egg | /help"))
# presence = interactions.Presence(activities=act_list)

with open("config.json", "r") as f:
    config = json.load(f)
    TOKEN = config["TOKEN"]
    COMMAND_PREFIX = config["COMMAND_PREFIX"]

dpy_bot = dpy_commands.Bot(command_prefix=COMMAND_PREFIX, intents=dpy_intents)
bot = interactions.Client(token=TOKEN, intents=intents)

# TODO Cogs with interactions 4.1
# dpy_bot.load_extension("extensions.user_utils")
# dpy_bot.load_extension("extensions.coop")
# coop = dpy_bot.get_cog("Coop")
# user_utils = dpy_bot.get_cog("UserUtils")

#endregion

#region Main Events

@dpy_bot.event
async def on_ready():
    await dpy_bot.change_presence(activity=dpy.Game("Egg Inc with Wall-Egg | /help"))
    print("Bot is ready")

async def reload_extensions():
    print()
    # dpy_bot.reload_extension("extensions.user_utils")
    # dpy_bot.reload_extension("extensions.coop")

@bot.event
async def on_guild_create(guild: interactions.Guild):
    with open("config.json", "r") as f:
        config = json.load(f)
    if str(guild.id) not in config["guilds"].keys(): 
        # New guild registration

        # Config file
        config["guilds"][str(guild.id)] = {
            "COOPS_BEFORE_AFK": 3,
            "GUEST_ROLE_ID": "",
            "KEEP_COOP_CHANNELS": False,
            "USE_EMBEDS": True
            }
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        await reload_extensions()
        
        data = await bot._http.get_channel(guild.system_channel_id)
        main_channel = interactions.Channel(**data, _client=bot._http)

        # Fix if working with interactions <= 4.0.2 (fixed in unstable)
        # guild.roles = [interactions.Role(**role, _client=bot._http) for role in guild.roles]

        # Creates Coop Organizer, Coop Creator, AFK and Alt roles if not exist
        coop_role = [role for role in guild.roles if role.name == "Coop Organizer"]
        creator_role = [role for role in guild.roles if role.name == "Coop Creator"]
        afk_role = [role for role in guild.roles if role.name == "AFK"]
        alt_role = [role for role in guild.roles if role.name == "Alt"]

        role_error = False
        bot_role = [role for role in guild.roles if role.name == bot.me.name]
        if not bot_role:
            await main_channel.send("ERROR: Bot role not found")
            return

        if coop_role and coop_role.position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the Coop Organizer below the bot role")
        elif not coop_role:
            coop_role = await guild.create_role(name="Coop Organizer", mentionable=True, reason="Chicken3PO feature")
            await main_channel.send("Coop Organizer role created")
        if creator_role and creator_role.position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the Coop Creator below the bot role")
        elif not creator_role:
            creator_role = await guild.create_role(name="Coop Creator", reason="Chicken3PO feature")
            await main_channel.send("Coop Creator role created")
        if afk_role and afk_role.position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the AFK below the bot role")
        elif not afk_role:
            afk_role = await guild.create_role(name="AFK", reason="Chicken3PO feature")
            await main_channel.send("AFK role created")
        if alt_role and alt_role.position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the Alt below the bot role")
        elif not alt_role:
            alt_role = await guild.create_role(name="Alt", reason="Chicken3PO feature")
            await main_channel.send("Alt role created")
        
        if role_error:
            await main_channel.send("Bot setup incomplete, please make changes and retry :x:")
        else:
            await main_channel.send("Bot setup done :white_check_mark:")

@bot.event
async def on_guild_member_remove(member: interactions.GuildMembers):
    if int(member.user.id) == int(bot.me.id):
        with open("config.json", "r") as f:
            config = json.load(f)
        if str(member.guild_id) in config["guilds"].keys():
            config["guilds"].pop(str(member.guild_id))
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
            await reload_extensions()

#endregion

#region Owner Commands

@dpy_bot.command(name="reloadext")
@dpy_commands.is_owner()
async def reload_extensions_command(ctx):
    try:
        await reload_extensions()
    except Exception as inst:
        await ctx.send(f"Administrative error (#1) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send("All extensions have been reloaded :arrows_counterclockwise:")

@dpy_bot.command(name="serverlist")
@dpy_commands.is_owner()
async def get_server_list(ctx):

    dm_channel = ctx.author.dm_channel
    if dm_channel == None:
        await ctx.author.create_dm()
        dm_channel = ctx.author.dm_channel

    liste = {}
    for guild in dpy_bot.guilds:
        liste[guild.name] = guild.id
    await dm_channel.send(liste)

@dpy_bot.command(name="removeserver")
@dpy_commands.is_owner()
async def remove_from_server(ctx, id):
    try:
        guild = await dpy_bot.fetch_guild(id)
        await guild.leave()
    except Exception as inst:
        await ctx.send(f"Administrative error (#2) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send(f"Left {guild.name} :wink:")

@dpy_bot.command(name="getdatafile")
@dpy_commands.is_owner()
async def get_data_file(ctx, filename):

    dm_channel = ctx.author.dm_channel
    if dm_channel == None:
        await ctx.author.create_dm()
        dm_channel = ctx.author.dm_channel
    
    try:
        with open(f"data/{filename}.json", "rb") as f:
            await dm_channel.send(file=dpy.File(f))
    except Exception as inst:
        await ctx.send(f"Administrative error (#3) :confounded:\n```{type(inst)}\n{inst}```")
        return

@dpy_bot.command(name="modifydatafile")
@dpy_commands.is_owner()
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

#endregion

# TODO on_slash_command_error re-implement elsewhere
#region Command Events

@dpy_bot.event
async def on_command_error(ctx, error):
    if isinstance(error, dpy_commands.MissingRequiredArgument):
        await ctx.send("Something is missing from this command :thinking:")
    else:
        print(error)

# @bot.event
# async def on_slash_command_error(ctx, error):
#     if isinstance(error, CheckFailure):
#         if any(substring in ctx.name for substring in ["Remove contract", "Coop completed", "Coop failed"]):
#             await ctx.send("Unauthorized target message :no_entry_sign:", hidden=True)
#         elif discord.utils.get(ctx.guild.roles, name="AFK") in ctx.author.roles:
#             await ctx.send("Unauthorized command as AFK :no_entry_sign:", hidden=True)
#         else:
#             await ctx.send("Unauthorized channel for this command :no_entry_sign:", hidden=True)
#     elif isinstance(error, commands.CheckAnyFailure):
#         await ctx.send("Unauthorized command :no_entry_sign:", hidden=True)
#     else:
#         print(error)

#endregion

#region Client Start

dpy_bot.remove_command("help")

loop = asyncio.get_event_loop()

task2 = loop.create_task(dpy_bot.start(TOKEN, bot=True))
task1 = loop.create_task(bot._ready())

gathered = asyncio.gather(task1, task2, loop=loop)
loop.run_until_complete(gathered)

#endregion
