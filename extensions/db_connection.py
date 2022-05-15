import discord as pycord
import interactions
from pymongo import MongoClient

import extensions.utils as utils

import json
from typing import *

# JSON_PATH = "data/"

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

def load_db_connection():
    db_hostname = utils.read_config("DB_HOSTNAME")
    db_port = utils.read_config("DB_PORT")
    db_name = utils.read_config("DB_NAME")
    return DatabaseConnection(db_hostname, db_port, db_name)

class DatabaseConnection():

    def __init__(self, hostname, port, database_name):
        self.client = MongoClient(hostname, port)
        self.db = self.client[database_name]
        self.guild_config = self.db.guild_config
        self.alt_index = self.db.alt_index
        self.running_coops = self.db.running_coops
        self.participation_archive = self.db.participation_archive

#region Guild config
    
    def get_all_guild_ids(self) -> List[int]:
        return [doc["guild_id"] for doc in self.guild_config.find()]
    
    def get_guild_config_value(self, guild_id: int, key: str) -> Union[str, int, bool, None]:
        if doc := self.guild_config.find_one({"guild_id": guild_id}) and key in doc.keys():
            return doc[key]
        else:
            return None

    def set_guild_config_value(self, guild_id: int, key: str, value):
        self.guild_config.update_one({"guild_id": guild_id}, {"$set": {key: value}})

#endregion
