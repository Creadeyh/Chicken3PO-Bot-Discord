import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext

import extensions.utils as utils

import json

with open("config.json", "r") as f:
    config = json.load(f)
    if config["guilds"]:
        GUILD_IDS = list(map(int, config["guilds"].keys()))
    else:
        GUILD_IDS = []

class Commands(interactions.Extension):

    def __init__(self, bot, pycord_bot):
        self.bot: interactions.Client = bot
        self.pycord_bot: pycord_commands.Bot = pycord_bot
    
    #region Alt account commands

    @interactions.extension_command(
        name="register-alt",
        description="Registers an alt EggInc account for the Discord account",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="member",
                description="The Discord account",
                type=interactions.OptionType.USER,
                required=True
            ),
            interactions.Option(
                name="name_main",
                description="The EggInc name of the main account",
                type=interactions.OptionType.STRING,
                required=True
            ),
            interactions.Option(
                name="name_alt",
                description="The EggInc name of the alt account",
                type=interactions.OptionType.STRING,
                required=True
            )
        ])
    # TODO Owner and admin permissions
    async def register_alt_account(self, ctx: ComponentContext, member: interactions.Member, name_main: str, name_alt: str):
        
        if type(member) != interactions.Member:
            await ctx.send(":warning: This user is not in the guild", ephemeral=True)
            return

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))

        pycord_member: pycord.Member = ctx_guild.get_member(int(member.id))
        alt_role = pycord.utils.get(ctx_guild.roles, name="Alt")
        if alt_role in pycord_member.roles:
            await ctx.send(":warning: This user already has an alt account", ephemeral=True)
            return

        await pycord_member.add_roles(alt_role)

        alt_dic = utils.read_json("alt_index")
        alt_dic[str(pycord_member.id)] = {
            "main": name_main,
            "alt": name_alt
        }
        utils.save_json("alt_index", alt_dic)

        await ctx.send("Alt account registered :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="unregister-alt",
        description="Unregisters the alt EggInc account for the Discord account",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="member",
                description="The Discord account",
                type=interactions.OptionType.USER,
                required=True
            )
        ])
    # TODO Owner and admin permissions
    async def unregister_alt_account(self, ctx: ComponentContext, member: interactions.Member):

        if type(member) != interactions.Member:
            await ctx.send(":warning: This user is not in the guild", ephemeral=True)
            return
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))

        pycord_member: pycord.Member = ctx_guild.get_member(int(member.id))
        alt_role = utils.get(ctx_guild.roles, name="Alt")
        if alt_role not in pycord_member.roles:
            await ctx.send(":warning: This user has no alt account", ephemeral=True)
            return

        await pycord_member.remove_roles(alt_role)

        alt_dic = utils.read_json("alt_index")
        alt_dic.pop(str(member.id))
        utils.save_json("alt_index", alt_dic)

        await ctx.send("Alt account unregistered :white_check_mark:", ephemeral=True)

    #endregion

    #region Misc Commands

    @interactions.extension_command(
        name="settings",
        description="Changes a setting value of the bot for the guild",
        scope=GUILD_IDS,
        options=[
            interactions.Option(
                name="setting",
                description="The setting to change",
                type=interactions.OptionType.STRING,
                required=True,
                choices=[
                    interactions.Choice(
                        name="Number of coops missed before AFK",
                        value="COOPS_BEFORE_AFK"
                    ),
                    interactions.Choice(
                        name="ID of the guest role which isn't taking part in coops",
                        value="GUEST_ROLE_ID"
                    ),
                    interactions.Choice(
                        name="Whether or not to keep coop channel after the coop has been marked completed or failed (true/false)",
                        value="KEEP_COOP_CHANNELS"
                    ),
                    interactions.Choice(
                        name="Whether or not to use embeds, as mentions don't display on mobile if user not in cache (true/false)",
                        value="USE_EMBEDS"
                    )
                ]
            ),
            interactions.Option(
                name="value",
                description="The value to set",
                type=interactions.OptionType.STRING,
                required=True
            )
        ]
    )
    # TODO Owner and admin permissions
    async def settings(self, ctx: CommandContext, setting: str, value):

        if setting in ["COOPS_BEFORE_AFK", "GUEST_ROLE_ID"]:
            try:
                value = int(value)
            except Exception:
                await ctx.send(":warning: Invalid value", ephemeral=True)
                return
        elif setting in ["KEEP_COOP_CHANNELS", "USE_EMBEDS"]:
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            else:
                await ctx.send(":warning: Invalid value", ephemeral=True)
                return
            
        with open("config.json", "r") as f:
            config = json.load(f)
        config["guilds"][str(ctx.guild_id)][setting] = value
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)

        await ctx.send(f"Changed the value of {setting} to {value} :white_check_mark:", ephemeral=True)

    @interactions.extension_command(
        name="help",
        description="Help command",
        scope=GUILD_IDS
    )
    # TODO Redo with better layout
    async def help(self, ctx: CommandContext):
        await ctx.send("__**Chicken3PO Commands**__\n\n", ephemeral=True)

        await ctx.send("`&setuphere`\n" +
                        "- Admins only\n" +
                        "- Defines the channel as reserved for bot commands\n\n" +

                        "`/settings [setting] [value]`\n" +
                        "- Admins only\n" +
                        "- Changes a setting value of the bot for the guild\n" +
                        "- *setting* = The setting to change\n" +
                        "- *value* = The value to set\n\n" +

                        "`/contract [contract-id] [size] [is-leggacy]`\n" +
                        "- Admins and coop organizers only\n" +
                        "- Registers a new contract and creates a channel and category for it\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *size* = Number of slots available in the contract\n" +
                        "- *is-leggacy* = Whether the contract is leggacy or not\n\n" +

                        "`/coop [contract-id] [coop-code] [locked]`\n" +
                        "- Registers a new coop and displays it in the contract channel\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-code* = The code to join the coop\n" +
                        "- *locked* = Whether or not the coop is locked at creation. Prevents people from joining\n\n" +

                        "`/lock [contract-id] [coop-nb]`\n" +
                        "- Admins, coop organizers and coop creators only\n" +
                        "- Locks a coop, preventing people from joining\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-nb* = The number of the coop. If not given, looks for the coop of which you are the creator\n\n" +

                        "`/unlock [contract-id] [coop-nb]`\n" +
                        "- Admins, coop organizers and coop creators only\n" +
                        "- Unlocks a coop, allowing people to join again\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-nb* = The number of the coop. If not given, looks for the coop of which you are the creator\n\n",
                        ephemeral=True)

        await ctx.send("`/kick [member] [contract-id] [coop-nb]`\n" +
                        "- Admins, coop organizers and coop creators only\n" +
                        "- Kicks someone from a coop\n" +
                        "- *member* = The member to be kicked from the coop\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-nb* = The number of the coop. If not given, looks for the coop of which you are the creator\n\n" +

                        "`/codes [contract-id]`\n" +
                        "- Admins and coop organizers only\n" +
                        "- Sends the codes of currently running coops\n" +
                        "- *contract-id* = The contract for which you want the coop codes. If not given, sends for all running contracts\n\n" +

                        "`/register-alt [member] [name_main] [name_alt]`\n" +
                        "- Admins only\n" +
                        "- Registers an alt EggInc account for the Discord account\n" +
                        "- *member* = The Discord account\n" +
                        "- *name-main* = The EggInc name of the main account\n" +
                        "- *name-alt* = The EggInc name of the alt account\n\n" +

                        "`/unregister-alt [member]`\n" +
                        "- Admins only\n" +
                        "- Unregisters the alt EggInc account for the Discord account\n" +
                        "- *member* = The Discord account\n\n" +

                        "`/coop-completed [contract_id] [coop_nb]`\n" +
                        "OR *Right click on coop message -> Applications -> `Coop completed`*\n" +
                        "- Admins, coop organizers and coop creators only\n" +
                        "- Marks the coop as completed\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-nb* = The number of the coop. If not given, looks for the coop of which you are the creator\n\n" +

                        "`/coop-failed [contract_id] [coop_nb]`\n" +
                        "OR *Right click on coop message -> Applications -> `Coop failed`*\n" +
                        "- Admins, coop organizers and coop creators only\n" +
                        "- Marks the coop as failed. Returns members to the remaining list\n" +
                        "- *contract-id* = The unique ID for an EggInc contract\n" +
                        "- *coop-nb* = The number of the coop. If not given, looks for the coop of which you are the creator\n\n" +

                        "`/contract-remove [contract_id]`\n" +
                        "OR *Right click on contract message -> Applications -> `Remove contract`*\n" +
                        "- Admins and coop organizers only\n" +
                        "- If all coops are completed/failed, deletes the contract channel and category\n" +
                        "- *contract-id* = The unique ID for an EggInc contract",
                        ephemeral=True)

    #endregion

def setup(bot, pycord_bot):
    Commands(bot, pycord_bot)
