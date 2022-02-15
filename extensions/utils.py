import discord
import json

#region JSON Utils

JSON_PATH = "data/"

def read_guild_config(guild_id, key):
    with open("config.json", "r") as f:
        config = json.load(f)
    return config["guilds"][str(guild_id)][key]

def read_json(name):
    try:
        with open(f"{JSON_PATH}{name}.json", "r") as f:
            dic = json.load(f)
    except FileNotFoundError:
        dic = {}
        with open(f"{JSON_PATH}{name}.json", "w") as f:
            json.dump(dic, f, indent=4)
    return dic

def save_json(name, dic):
    with open(f"{JSON_PATH}{name}.json", "w") as f:
        json.dump(dic, f, indent=4)

#endregion

async def get_member_mention(member_id, guild, bot):
    # Id is an alt account
    if str(member_id).startswith("alt"):
        alt_dic = read_json("alt_index")
        main_id = member_id.replace("alt", "")
        return guild.get_member(int(main_id)).mention + f"({alt_dic[main_id]['alt']})"
    # Member has left the guild
    elif member_id not in [mem.id for mem in guild.members]:
        return (await bot.fetch_user(member_id)).mention
    # Reference to main account if member has an alt
    elif discord.utils.get(guild.roles, name="Alt") in guild.get_member(member_id).roles:
        alt_dic = read_json("alt_index")
        return guild.get_member(member_id).mention + f"({alt_dic[str(member_id)]['main']})"
    # Member is in the guild and doesn't have an alt
    else:
        return guild.get_member(member_id).mention

def get_coop_embed(coop_nb, contract_size, creator_mention = None, other_members_mentions = [], color = discord.Color.random()):

    if creator_mention:
        title = f"Coop {coop_nb} - {len(other_members_mentions)+1}/{contract_size}{' FULL' if (len(other_members_mentions)+1) == contract_size else ''}"
        desc = f"**Members:**\n- {creator_mention} (Creator)"
        for mention in other_members_mentions:
            desc = desc + f"\n- {mention}"
    else:
        title = f"Coop {coop_nb}"
        desc = ""
    
    return discord.Embed(color=color, title=title, description=desc)

def get_coop_content(coop_nb, contract_size, creator_mention = None, other_members_mentions = []):

    text = "> -------------------------\n"

    if creator_mention:
        text = text + f"> **Coop {coop_nb} - {len(other_members_mentions)+1}/{contract_size}{' FULL' if (len(other_members_mentions)+1) == contract_size else ''}**\n> \n"
        text = text + f"> **Members:**\n> - {creator_mention} (Creator)\n"

        for mention in other_members_mentions:
            text = text + f"> - {mention}\n"
    else:
        text = text + f"> **Coop {coop_nb}**\n"
    
    text = text + "> -------------------------"
    return text

def is_member_active_in_running_coops(member_id):
    running_coops = read_json("running_coops")
    for contract in running_coops.values():
        for coop in contract["coops"]:
            if member_id in coop["members"]:
                return True
    return False
