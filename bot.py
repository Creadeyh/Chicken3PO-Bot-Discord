import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions.ext import wait_for

import extensions.utils as utils
import extensions.db_connection as db

import json
import asyncio
from datetime import datetime

#region Inits

print(f"{datetime.now().isoformat()} Starting up...")

pycord_intents = pycord.Intents.default()
pycord_intents.members = True
pycord_intents.message_content = True
intents = interactions.Intents.DEFAULT | interactions.Intents.GUILD_MEMBERS

TOKEN = utils.read_config("TOKEN")
COMMAND_PREFIX = utils.read_config("COMMAND_PREFIX")

pycord_bot = pycord_commands.Bot(command_prefix=COMMAND_PREFIX, intents=pycord_intents, auto_sync_commands=False)
# RELEASE
bot = interactions.Client(token=TOKEN, intents=intents)
# DEBUG
# bot = interactions.Client(token=TOKEN, intents=intents, disable_sync=True)

wait_for.setup(bot, add_method=True)

db_connection = db.DatabaseConnection()

bot.load("extensions.commands", None, pycord_bot, db_connection)
bot.load("extensions.contract", None, pycord_bot, db_connection)
bot.load("extensions.coop", None, pycord_bot, db_connection)

#endregion

#region Main Events

@pycord_bot.event
async def on_ready():
    await pycord_bot.change_presence(activity=pycord.Game("Egg Inc with Wall-Egg | /help"))
    print(f"{datetime.now().isoformat()} Bot is ready")

async def reload_extensions():
    bot.reload("extensions.commands", None, pycord_bot, db_connection)
    bot.reload("extensions.contract", None, pycord_bot, db_connection)
    bot.reload("extensions.coop", None, pycord_bot, db_connection)

# FYI: Event is always fired for every guild at bot startup
@bot.event
async def on_guild_create(guild: interactions.Guild):
    
    if int(guild.id) not in db_connection.get_all_guild_ids():
        # New guild registration

        # Guild config
        db_connection.guild_config.insert_one({
            "guild_id": int(guild.id),
            "COOPS_BEFORE_AFK": 3,
            "GUEST_ROLE_ID": "",
            "KEEP_COOP_CHANNELS": False
        })
        await reload_extensions()

        # Data documents
        db_connection.alt_index.insert_one({"guild_id": int(guild.id), "data": {}})
        
        data = await bot._http.get_channel(guild.system_channel_id)
        main_channel = interactions.Channel(**data, _client=bot._http)

        # Creates Coop Organizer, Coop Creator, AFK and Alt roles if not exist
        coop_role = [role for role in guild.roles if role.name == "Coop Organizer"]
        creator_role = [role for role in guild.roles if role.name == "Coop Creator"]
        afk_role = [role for role in guild.roles if role.name == "AFK"]
        alt_role = [role for role in guild.roles if role.name == "Alt"]

        role_error = False
        bot_role = [role for role in guild.roles if role.name == bot.me.name]
        if bot_role:
            bot_role = bot_role[0]
        else:
            await main_channel.send("ERROR: Bot role not found")
            return

        if coop_role and coop_role[0].position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the Coop Organizer below the bot role")
        elif not coop_role:
            coop_role = await guild.create_role(name="Coop Organizer", mentionable=True, reason="Chicken3PO feature")
            await main_channel.send("Coop Organizer role created")
        if creator_role and creator_role[0].position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the Coop Creator below the bot role")
        elif not creator_role:
            creator_role = await guild.create_role(name="Coop Creator", reason="Chicken3PO feature")
            await main_channel.send("Coop Creator role created")
        if afk_role and afk_role[0].position > bot_role.position:
            role_error = True
            await main_channel.send("Please move the AFK below the bot role")
        elif not afk_role:
            afk_role = await guild.create_role(name="AFK", reason="Chicken3PO feature")
            await main_channel.send("AFK role created")
        if alt_role and alt_role[0].position > bot_role.position:
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
        db_connection.guild_config.delete_one({"guild_id": int(member.guild_id)})
        db_connection.alt_index.delete_one({"guild_id": int(member.guild_id)})
        db_connection.running_coops.delete_many({"guild_id": int(member.guild_id)})
        db_connection.participation_archive.delete_many({"guild_id": int(member.guild_id)})
        await reload_extensions()

#endregion

#region Owner Commands (use in DM)

@pycord_bot.command(name="reloadext")
@pycord_commands.is_owner()
async def reload_extensions_command(ctx):
    try:
        await reload_extensions()
    except Exception as inst:
        await ctx.send(f"Administrative error (#1) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send("All extensions have been reloaded :arrows_counterclockwise:")

@pycord_bot.command(name="serverlist")
@pycord_commands.is_owner()
async def get_server_list(ctx):

    dm_channel = ctx.author.dm_channel
    if dm_channel == None:
        await ctx.author.create_dm()
        dm_channel = ctx.author.dm_channel

    liste = {}
    for guild in pycord_bot.guilds:
        liste[guild.name] = guild.id
    await dm_channel.send(liste)

@pycord_bot.command(name="removeserver")
@pycord_commands.is_owner()
async def remove_from_server(ctx, id):
    try:
        guild = await pycord_bot.fetch_guild(id)
        await guild.leave()
    except Exception as inst:
        await ctx.send(f"Administrative error (#2) :confounded:\n```{type(inst)}\n{inst}```")
        return
    else:
        await ctx.send(f"Left {guild.name} :wink:")

@pycord_bot.command(name="update-data-version")
@pycord_commands.is_owner()
async def update_data_version(ctx: pycord_commands.Context):
    with open("config.json", "r") as f:
        config = json.load(f)
    
    if config["BOT_VERSION"] == "2.0.0":
        config["BOT_VERSION"] = "2.1.0"

        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        await ctx.send("Successfully updated data to 2.1.0 :white_check_mark:")
    else:
        await ctx.send("No data update is needed")

#endregion

#region Command Events

@pycord_bot.event
async def on_command_error(ctx, error):
    if isinstance(error, pycord_commands.MissingRequiredArgument):
        await ctx.send("Something is missing from this command :thinking:")
    else:
        print(f"{datetime.now().isoformat()} {error}")

#endregion

#region Client Start

pycord_bot.remove_command("help")

loop = asyncio.get_event_loop()

task2 = loop.create_task(pycord_bot.start(TOKEN))
task1 = loop.create_task(bot._ready())

gathered = asyncio.gather(task1, task2, loop=loop)
loop.run_until_complete(gathered)

#endregion
