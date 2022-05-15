import discord as pycord
import interactions

import json
from typing import *

#region JSON utils

# JSON_PATH = "data/"

def read_config(key: str) -> Union[str, int]:
    with open("config.json", "r") as f:
        config = json.load(f)
    return config[key]

# def read_guild_config(guild_id, key):
#     with open("config.json", "r") as f:
#         config = json.load(f)
#     return config["guilds"][str(guild_id)][key]

# def read_json(name):
#     try:
#         with open(f"{JSON_PATH}{name}.json", "r") as f:
#             dic = json.load(f)
#     except FileNotFoundError:
#         dic = {}
#         with open(f"{JSON_PATH}{name}.json", "w") as f:
#             json.dump(dic, f, indent=4)
#     return dic

# def save_json(name, dic):
#     with open(f"{JSON_PATH}{name}.json", "w") as f:
#         json.dump(dic, f, indent=4)

#endregion

#region Member utils

async def get_member_mention(member_id: int, guild: pycord.Guild, bot: pycord.Client) -> str:
    # Id is an alt account
    if str(member_id).startswith("alt"):
        alt_dic = read_json("alt_index")
        main_id = member_id.replace("alt", "")
        return guild.get_member(int(main_id)).mention + f"({alt_dic[main_id]['alt']})"
    # Member has left the guild
    elif member_id not in [mem.id for mem in guild.members]:
        return (await bot.fetch_user(member_id)).mention
    # Reference to main account if member has an alt
    elif pycord.utils.get(guild.roles, name="Alt") in guild.get_member(member_id).roles:
        alt_dic = read_json("alt_index")
        return guild.get_member(member_id).mention + f"({alt_dic[str(member_id)]['main']})"
    # Member is in the guild and doesn't have an alt
    else:
        return guild.get_member(member_id).mention

def is_member_active_in_any_running_coops(member_id: int) -> bool:
    running_coops = read_json("running_coops")
    for contract in running_coops.values():
        for coop in contract["coops"]:
            if member_id in coop["members"]:
                return True
    return False

#endregion

#region Contract message utils

async def generate_contract_message_content_component(pycord_bot: pycord.Client, guild: pycord.Guild, contract_id: str) -> Tuple[str, Union[interactions.Button, None]]:
    running_coops = read_json("running_coops")

    if contract_id not in running_coops.keys():
        raise Exception("contract_id is not running")

    is_leggacy = running_coops[contract_id]["is_leggacy"]

    if is_leggacy:
        already_done_mentions = []
        for id in running_coops[contract_id]["already_done"]:
            already_done_mentions.append(await get_member_mention(id, guild, pycord_bot))
    remaining_mentions = []
    for id in running_coops[contract_id]["remaining"]:
        remaining_mentions.append(await get_member_mention(id, guild, pycord_bot))

    content = ("==============================\n"
                        + f"**{'LEGGACY ' if is_leggacy else ''}Contract available**\n"
                        + f"*Contract ID:* `{contract_id}`\n"
                        + f"*Coop size:* {running_coops[contract_id]['size']}\n"
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

async def update_contract_message(bot: interactions.Client, pycord_bot: pycord.Client, guild: pycord.Guild, contract_id) -> interactions.Message:
    running_coops = read_json("running_coops")

    if contract_id not in running_coops.keys():
        raise Exception("contract_id is not running")

    data = await bot._http.get_message(running_coops[contract_id]["channel_id"], running_coops[contract_id]["message_id"])
    message: interactions.Message = interactions.Message(**data, _client=bot._http)

    new_content, button = await generate_contract_message_content_component(pycord_bot, guild, contract_id)
    return await message.edit(content=new_content, components=button)

#endregion

#region Coop message utils

async def generate_coop_message_content_component(pycord_bot: pycord.Client, guild: pycord.Guild, contract_id: str, coop_nb: int) -> Tuple[str, Union[interactions.Button, None]]:
    running_coops = read_json("running_coops")

    if contract_id not in running_coops.keys():
        raise Exception("contract_id is not running")
    if coop_nb > len(running_coops[contract_id]["coops"]):
        raise Exception("Invalid coop number")

    coop_dic = running_coops[contract_id]["coops"][coop_nb-1]
    is_full = len(coop_dic["members"]) == running_coops[contract_id]["size"]
    is_failed = coop_dic["completed_or_failed"] == "failed"
    contract_size = running_coops[contract_id]["size"]

    if not is_failed:
        creator_mention = await get_member_mention(coop_dic["creator"], guild, pycord_bot)
        other_members_mentions = [await get_member_mention(member_id, guild, pycord_bot) for member_id in coop_dic["members"]]
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
    if coop_dic["completed_or_failed"] == False:
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
    elif coop_dic["completed_or_failed"] == "completed":
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

async def update_coop_message(bot: interactions.Client, pycord_bot: pycord.Client, guild: pycord.Guild, contract_id: str, coop_nb: int) -> interactions.Message:
    running_coops = read_json("running_coops")

    if contract_id not in running_coops.keys():
        raise Exception("contract_id is not running")
    if coop_nb > len(running_coops[contract_id]["coops"]):
        raise Exception("Invalid coop number")

    data = await bot._http.get_message(running_coops[contract_id]["channel_id"], running_coops[contract_id]["coops"][coop_nb-1]["message_id"])
    interac_message: interactions.Message = interactions.Message(**data, _client=bot._http)

    new_content, button = await generate_coop_message_content_component(pycord_bot, guild, contract_id, coop_nb)
    return await interac_message.edit(content=new_content, components=button)

#endregion

#region Misc utils

async def send_notif_no_remaining(guild: pycord.Guild, contract_id: str):
    orga_role = pycord.utils.get(guild.roles, name="Coop Organizer")

    running_coops = read_json("running_coops")
    contract_channel = guild.get_channel(running_coops[contract_id]["channel_id"])
    
    await contract_channel.send(f"{orga_role.mention} Everyone has joined a coop for this contract :tada:")

#endregion