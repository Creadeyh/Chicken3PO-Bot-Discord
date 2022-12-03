import discord as pycord
import interactions

import extensions.db_connection as db
from extensions.checks import check_is_id_afk

import json
from typing import *

from extensions.enums import CoopStatusEnum

def read_config(key: str) -> Union[str, int]:
    with open("config.json", "r") as f:
        config = json.load(f)
    return config[key]

def load_db_connection():
    db_string = read_config("DB_STRING")
    db_name = read_config("DB_NAME")
    return db.DatabaseConnection(db_string, db_name)

#region Member utils

async def get_member_mention(member_id: int, guild: pycord.Guild, bot: pycord.Client, db_connection: db.DatabaseConnection) -> str:
    # Id is an alt account
    if str(member_id).startswith("alt"):
        main_id = member_id.replace("alt", "")
        return guild.get_member(int(main_id)).mention + f"({db_connection.get_alt_alt_name(guild.id, main_id)})"
    # Member has left the guild
    elif member_id not in [mem.id for mem in guild.members]:
        return (await bot.fetch_user(member_id)).mention
    # Reference to main account if member has an alt
    elif pycord.utils.get(guild.roles, name="Alt") in guild.get_member(member_id).roles:
        return guild.get_member(member_id).mention + f"({db_connection.get_alt_main_name(guild.id, member_id)})"
    # Member is in the guild and doesn't have an alt
    else:
        return guild.get_member(member_id).mention

def is_member_active_in_any_running_coops(member_id: int, db_connection: db.DatabaseConnection, guild_id: int) -> bool:
    if db_connection.running_coops.find_one({"guild_id": guild_id, "coops.members": member_id}) != None:
        return True
    else:
        return False

#endregion

#region Contract message utils

async def generate_contract_message_content_component(pycord_bot: pycord.Client, db_connection: db.DatabaseConnection, guild: pycord.Guild, contract_id: str) -> Tuple[str, Union[interactions.Button, None]]:

    if not db_connection.is_contract_running(guild.id, contract_id):
        raise Exception("contract_id is not running")

    contract_dic = db_connection.get_running_contract(guild.id, contract_id)
    is_leggacy = contract_dic["is_leggacy"]

    if is_leggacy:
        already_done_mentions = []
        for id in contract_dic["already_done"]:
            if not check_is_id_afk(id, guild):
                already_done_mentions.append(await get_member_mention(id, guild, pycord_bot, db_connection))
    remaining_mentions = []
    for id in contract_dic["remaining"]:
        remaining_mentions.append(await get_member_mention(id, guild, pycord_bot, db_connection))

    content = ("==============================\n"
                        + f"**{'LEGGACY ' if is_leggacy else ''}Contract available**\n"
                        + f"*Contract ID:* `{contract_id}`\n"
                        + f"*Coop size:* {contract_dic['size']}\n"
                        + "==============================\n\n"
                        + (
                            (
                                f"**Already done:**\n{''.join(already_done_mentions)}"
                                + ("\n" if already_done_mentions else "")
                                + "\n"
                            )
                            if is_leggacy else ""
                        )
                        + f"**Remaining: ({len(remaining_mentions)})**\n{''.join(remaining_mentions)}\n"
                    )
    if is_leggacy:
        button = interactions.Button(
            style=interactions.ButtonStyle.PRIMARY,
            label="I've already done this contract",
            custom_id=f"leggacy_{contract_id}"
        )
    else:
        button = None

    return content, button

async def update_contract_message(
    bot: interactions.Client,
    pycord_bot: pycord.Client,
    db_connection: db.DatabaseConnection,
    guild: pycord.Guild,
    contract_id
) -> interactions.Message:
    if not db_connection.is_contract_running(guild.id, contract_id):
        raise Exception("contract_id is not running")

    contract_dic = db_connection.get_running_contract(guild.id, contract_id)

    data = await bot._http.get_message(contract_dic["channel_id"], contract_dic["message_id"])
    message: interactions.Message = interactions.Message(**data, _client=bot._http)

    new_content, button = await generate_contract_message_content_component(pycord_bot, db_connection, guild, contract_id)
    return await message.edit(content=new_content, components=button)

#endregion

#region Coop message utils

async def generate_coop_message_content_component(
    pycord_bot: pycord.Client,
    db_connection: db.DatabaseConnection,
    guild: pycord.Guild,
    contract_id: str,
    coop_nb: int
) -> Tuple[str, Union[interactions.Button, None]]:
    if not db_connection.is_contract_running(guild.id, contract_id):
        raise Exception("contract_id is not running")

    contract_dic = db_connection.get_running_contract(guild.id, contract_id)

    if coop_nb > len(contract_dic["coops"]):
        raise Exception("Invalid coop number")

    coop_dic = contract_dic["coops"][coop_nb-1]
    is_full = len(coop_dic["members"]) == contract_dic["size"]
    is_failed = coop_dic["completed_or_failed"] == CoopStatusEnum.FAILED.value
    contract_size = contract_dic["size"]

    if not is_failed:
        creator_mention = await get_member_mention(coop_dic["creator"], guild, pycord_bot, db_connection)
        other_members_mentions = [await get_member_mention(member_id, guild, pycord_bot, db_connection) for member_id in coop_dic["members"]]
        other_members_mentions.remove(creator_mention)

    content = "> -------------------------\n"
    if not is_failed:
        content = content + f"> **Coop {coop_nb} - {len(other_members_mentions)+1}/{contract_size}{' FULL' if (len(other_members_mentions)+1) == contract_size else ''}**\n> \n"
        content = content + f"> **Members:**\n> - {creator_mention} (Creator)\n"
        for mention in other_members_mentions:
            content = content + f"> - {mention}\n"
    else:
        content = content + f"> **Coop {coop_nb}**\n"
    content = content + "> -------------------------"

    button = None
    if coop_dic["completed_or_failed"] == CoopStatusEnum.RUNNING.value:
        if coop_dic["locked"]:
            button = interactions.Button(
                style=interactions.ButtonStyle.DANGER,
                label="LOCKED",
                custom_id=f"joincoop_{contract_id}_{coop_nb}",
                disabled=True
            )
        else:
            button = interactions.Button(
                style=interactions.ButtonStyle.SUCCESS,
                label="Join",
                custom_id=f"joincoop_{contract_id}_{coop_nb}",
                disabled=is_full
            )
    elif coop_dic["completed_or_failed"] == CoopStatusEnum.COMPLETED.value:
        button = interactions.Button(
            style=interactions.ButtonStyle.PRIMARY,
            label="COMPLETED",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=True
        )
    elif is_failed:
        button = interactions.Button(
            style=interactions.ButtonStyle.DANGER,
            label="FAILED",
            custom_id=f"joincoop_{contract_id}_{coop_nb}",
            disabled=True
        )

    return content, button

async def update_coop_message(
    bot: interactions.Client,
    pycord_bot: pycord.Client,
    db_connection: db.DatabaseConnection,
    guild: pycord.Guild,
    contract_id: str,
    coop_nb: int
) -> interactions.Message:
    if not db_connection.is_contract_running(guild.id, contract_id):
        raise Exception("contract_id is not running")

    contract_dic = db_connection.get_running_contract(guild.id, contract_id)

    if coop_nb > len(contract_dic["coops"]):
        raise Exception("Invalid coop number")

    data = await bot._http.get_message(contract_dic["channel_id"], contract_dic["coops"][coop_nb-1]["message_id"])
    interac_message: interactions.Message = interactions.Message(**data, _client=bot._http)

    new_content, button = await generate_coop_message_content_component(pycord_bot, db_connection, guild, contract_id, coop_nb)
    return await interac_message.edit(content=new_content, components=button)

#endregion

#region Misc utils

async def send_notif_no_remaining(db_connection: db.DatabaseConnection, guild: pycord.Guild, contract_id: str):
    orga_role = pycord.utils.get(guild.roles, name="Coop Organizer")

    contract_dic = db_connection.get_running_contract(guild.id, contract_id)
    contract_channel = guild.get_channel(contract_dic["channel_id"])
    
    await contract_channel.send(f"{orga_role.mention} Everyone has joined a coop for this contract :tada:")

#endregion