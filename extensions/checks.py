import discord as pycord
import interactions
from interactions import CommandContext

import extensions.db_connection as db

from typing import *

#region Contract checks

def check_contract_channel(db_connection: db.DatabaseConnection, guild_id: int, channel_id: int) -> Union[int, Literal[False]]:
    """
    Returns the contract_id if channel is a contract channel,
    else returns False
    """
    if (doc := db_connection.running_coops.find_one({"guild_id": guild_id, "channel_id": channel_id})) != None:
        return doc["contract_id"]
    else:
        return False

def check_context_menu_contract_message(db_connection: db.DatabaseConnection, guild_id: int, target_message_id: int) -> Union[int, Literal[False]]:
    """
    Returns the contract_id if target message is a contract message,
    else returns False
    """
    if (doc := db_connection.running_coops.find_one({"guild_id": guild_id, "message_id": target_message_id})) != None:
        return doc["contract_id"]
    else:
        return False

#endregion

#region Coop checks

def check_coop_channel(db_connection: db.DatabaseConnection, guild_id: int, channel_id: int) -> Union[Tuple[int, int], Literal[False]]:
    """
    Returns (contract_id, coop_nb) if channel is a coop channel,
    else returns False
    """
    # running_coops = db_connection.get_running_dic(guild_id)
    # for contract_id, contract in running_coops.items():
    #     for i in range(len(contract["coops"])):
    #         if contract["coops"][i]["channel_id"] == channel_id:
    #             return contract_id, i+1
    if (res := db_connection.running_coops.find_one(
        {"guild_id": guild_id, "coops.channel_id": channel_id},
        {"contract_id": 1, "coop_nb": {"$indexOfArray": ["$coops.channel_id", channel_id]}}
    )) != None:
        return res["contract_id"], res["coop_nb"]+1
    else:
        return False

def check_context_menu_coop_message(db_connection: db.DatabaseConnection, guild_id: int, target_message_id: int) -> Union[Tuple[int, int], Literal[False]]:
    """
    Returns (contract_id, coop_nb) if target message is a coop message,
    else returns False
    """
    # running_coops = db_connection.get_running_dic(guild_id)
    # for contract_id, contract in running_coops.items():
    #     for i in range(len(contract["coops"])):
    #         if contract["coops"][i]["message_id"] == target_message_id:
    #             return contract_id, i+1
    if (res := db_connection.running_coops.find_one(
        {"guild_id": guild_id, "coops.message_id": target_message_id},
        {"contract_id": 1, "coop_nb": {"$indexOfArray": ["$coops.message_id", target_message_id]}}
    )) != None:
        return res["contract_id"], res["coop_nb"]+1
    else:
        return False

#endregion

#region Permissions checks

async def check_is_owner(ctx: CommandContext):
    info = await ctx.client.get_current_bot_information()
    return int(ctx.author.user.id) == int(info["owner"]["id"])

def check_is_admin(ctx: CommandContext):
    # 8 is the administrator permission
    return (int(ctx.author.permissions) & 8)

def check_is_coop_organizer(author: pycord.Member, guild: pycord.Guild):
    organizer_role = pycord.utils.get(guild.roles, name="Coop Organizer")
    return organizer_role in author.roles

def check_is_coop_creator(
    author: pycord.Member,
    db_connection: db.DatabaseConnection,
    guild: pycord.Guild,
    contract_id: str,
    coop_nb: int
) -> bool:
    contract_dic = db_connection.get_running_contract(guild.id, contract_id)
    creator_role = pycord.utils.get(guild.roles, name="Coop Creator")
    return creator_role in author.roles and author.id == contract_dic["coops"][coop_nb-1]["creator"]

def check_is_afk(author: pycord.Member, guild: pycord.Guild):
    afk_role = pycord.utils.get(guild.roles, name="AFK")
    return afk_role in author.roles

#endregion
