from discord.ext import commands as dpy_commands
import interactions

import json

with open("config.json", "r") as f:
    config = json.load(f)
    if config["guilds"]:
        GUILD_IDS = list(map(int, config["guilds"].keys()))
    else:
        GUILD_IDS = []

class Commands(interactions.Extension):

    def __init__(self, bot):
        self.bot = bot

    #region Contract commands

    #endregion
    
    #region Misc Commands

    @command(
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
    async def settings(self, ctx: interactions.CommandContext, setting: str, value):

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

    @command(
        name="help",
        description="Command help",
        scope=GUILD_IDS
    )
    # TODO Redo with new commands and better layout
    async def help(self, ctx: interactions.CommandContext):
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


def setup(bot):
    Commands(bot)
