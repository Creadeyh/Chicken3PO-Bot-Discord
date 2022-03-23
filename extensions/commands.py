import discord as pycord
from discord.ext import commands as pycord_commands
import interactions
from interactions import CommandContext, ComponentContext

import extensions.checks as checks, extensions.utils as utils

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
    async def register_alt_account(self, ctx: ComponentContext, member: interactions.Member, name_main: str, name_alt: str):
        
        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))

        # Owner and admin permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if type(member) != interactions.Member:
            await ctx.send(":warning: This user is not in the guild", ephemeral=True)
            return

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
    async def unregister_alt_account(self, ctx: ComponentContext, member: interactions.Member):

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))

        # Owner and admin permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if type(member) != interactions.Member:
            await ctx.send(":warning: This user is not in the guild", ephemeral=True)
            return

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
    async def settings(self, ctx: CommandContext, setting: str, value):

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.get_member(int(ctx.author.user.id))

        # Owner and admin permissions
        if not (checks.check_is_owner(ctx_author, self.pycord_bot) or checks.check_is_admin(ctx_author)):
            await ctx.send(":x: Unauthorized", ephemeral=True)
            return

        if setting in ["COOPS_BEFORE_AFK", "GUEST_ROLE_ID"]:
            try:
                value = int(value)
            except Exception:
                await ctx.send(":warning: Invalid value", ephemeral=True)
                return
        elif setting in ["KEEP_COOP_CHANNELS"]:
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
    async def help(self, ctx: CommandContext):

        interac_guild = await ctx.get_guild()
        ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
        ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.id))

        embed, action_row_buttons, action_row_select = self.load_help(0, 0, checks.check_is_admin(ctx_author))
        await ctx.send(embeds=embed, components=[action_row_buttons, action_row_select], ephemeral=True)

    #endregion

    #region Events

    @interactions.extension_listener("on_component")
    async def help_event(self, ctx: ComponentContext):

        if ctx.data.custom_id.startswith("help_"):
            interac_guild = await ctx.get_guild()
            ctx_guild: pycord.Guild = await self.pycord_bot.fetch_guild(int(interac_guild.id))
            ctx_author: pycord.Member = await ctx_guild.fetch_member(int(ctx.author.id))

            if ctx.data.custom_id.startswith("help_button_"):
                split = ctx.data.custom_id.split("_")
                category = int(split[2])
                page = int(split[3])

                embed, action_row_buttons, action_row_select = self.load_help(category, page, checks.check_is_admin(ctx_author))
                await ctx.edit(embeds=embed, components=[action_row_buttons, action_row_select])
            
            elif ctx.data.custom_id.startswith("help_selectmenu"):
                category = int(ctx.data.values[0])
                page = 0

                embed, action_row_buttons, action_row_select = self.load_help(category, page, checks.check_is_admin(ctx_author))
                await ctx.edit(embeds=embed, components=[action_row_buttons, action_row_select])

    #endregion

    #region Misc methods

    def load_help(self, category: int, page: int, with_admin=False):
        with open("doc/help/help_data.json", "r") as f:
            help_dic = json.load(f)
        
        if not with_admin:
            del help_dic[1]
        
        embed_image = None
        if help_dic[category]["pages"][page]["image_url"]:
            embed_image = interactions.EmbedImageStruct(
                    url=help_dic[category]["pages"][page]["image_url"]
                )._json # TODO Remove ._json in next interactions version
        
        embed = interactions.Embed(
            title="__**Chicken3PO Commands**__",
            description=f"***{help_dic[category]['title']} - {page+1}/{len(help_dic[category]['pages'])}***",
            fields=[
                interactions.EmbedField(
                    name=help_dic[category]["pages"][page]["title"],
                    value=help_dic[category]["pages"][page]["content"]
                )
            ],
            image=embed_image
        )

        if page > 0:
            previous_page = page - 1
            previous_category = category
            prev_disabled = False
        else:
            if category > 0:
                previous_page = len(help_dic[category-1]["pages"]) - 1
                previous_category = category - 1
                prev_disabled = False
            else:
                previous_page, previous_category = "", ""
                prev_disabled = True
        
        if page < len(help_dic[category]["pages"])-1:
            next_page = page + 1
            next_category = category
            next_disabled = False
        else:
            if category < len(help_dic)-1:
                next_page = 0
                next_category = category + 1
                next_disabled = False
            else:
                next_page, next_category = "", ""
                next_disabled = True

        action_row_buttons = interactions.ActionRow(components=[
            interactions.Button(
                label="◀️",
                style=interactions.ButtonStyle.PRIMARY,
                custom_id=f"help_button_{previous_category}_{previous_page}",
                disabled=prev_disabled
            ),
            interactions.Button(
                label="▶️",
                style=interactions.ButtonStyle.PRIMARY,
                custom_id=f"help_button_{next_category}_{next_page}",
                disabled=next_disabled
            )
        ])

        select_options = []
        for i, dic in enumerate(help_dic):
            select_options.append(
                interactions.SelectOption(
                    label=f"{i+1}. {dic['title']}",
                    value=f"{i}",
                    default=True if i == category else False
                )
            )
        action_row_select = interactions.ActionRow(components=[
            interactions.SelectMenu(
                custom_id="help_selectmenu",
                options=select_options
            ),
        ])

        return embed, action_row_buttons, action_row_select

    #endregion

def setup(bot, pycord_bot):
    Commands(bot, pycord_bot)
