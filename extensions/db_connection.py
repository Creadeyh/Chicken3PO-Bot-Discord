from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from extensions.enums import ParticipationEnum, CoopStatusEnum, CoopGradeEnum

from typing import *

class DatabaseConnection():

    def __init__(self, connection_string, database_name):
        self.client = MongoClient(connection_string)
        try:
            self.client.admin.command('ping')
        except ConnectionFailure:
            print("Server not available")
        else:
            print("Connected to MongoDB")
        self.db = self.client[database_name]
        self.guild_config = self.db.guild_config
        self.alt_index = self.db.alt_index
        self.running_coops = self.db.running_coops
        self.participation_archive = self.db.participation_archive

#region Guild config
    
    def get_all_guild_ids(self) -> List[int]:
        return [doc["guild_id"] for doc in self.guild_config.find()]
    
    def get_guild_config_value(self, guild_id: int, key: str) -> Union[str, int, bool, None]:
        if (doc := self.guild_config.find_one({"guild_id": guild_id})) and key in doc.keys():
            return doc[key]
        else:
            return None

    def set_guild_config_value(self, guild_id: int, key: str, value):
        self.guild_config.update_one({"guild_id": guild_id}, {"$set": {key: value}})

#endregion

#region Alt index

    def add_alt_account(self, guild_id: int, member_id: int, name_main: str, name_alt: str):
        self.alt_index.update_one({"guild_id": guild_id}, {"$set":
            {
                f"data.{member_id}":
                    {
                        "main": name_main,
                        "alt": name_alt
                    }
            }
        })

    def remove_alt_account(self, guild_id: int, member_id: int):
        self.alt_index.update_one(
            {
                "guild_id": guild_id,
                f"data.{member_id}": {
                    "$exists": 1
                }
            },
            {
                "$unset": {f"data.{member_id}": ""}
            }
        )

    def get_alt_main_name(self, guild_id: int, member_id: int) -> Union[str, None]:
        if (doc := self.alt_index.find_one(
            {
                "guild_id": guild_id,
                f"data.{member_id}": {
                    "$exists": 1
                }
            }
        )):
            return doc["data"][str(member_id)]["main"]
        else:
            return None

    def get_alt_alt_name(self, guild_id: int, member_id: int) -> Union[str, None]:
        if (doc := self.alt_index.find_one(
            {
                "guild_id": guild_id,
                f"data.{member_id}": {
                    "$exists": 1
                }
            }
        )):
            return doc["data"][str(member_id)]["alt"]
        else:
            return None

#endregion

#region Contract checks

    def is_contract_running(self, guild_id: int, contract_id: str) -> bool:
        if self.running_coops.find_one({"guild_id": guild_id, "contract_id": contract_id}) != None:
            return True
        else:
            return False
    
    def is_contract_in_archive(self, guild_id: int, contract_id: str) -> bool:
        if self.participation_archive.find_one({"guild_id": guild_id, "contract_id": contract_id}) != None:
            return True
        else:
            return False
    
    def has_member_participated_in_previous_contract(self, guild_id: int, contract_id: str, member_id: int) -> Union[bool, None]:
        if (doc := self.participation_archive.find_one({"guild_id": guild_id, "contract_id": contract_id})) == None:
            return None
        for occurence in doc["data"].values():
            if (
                str(member_id) in occurence["participation"].keys()
                and occurence["participation"][str(member_id)] in [ParticipationEnum.YES.value, ParticipationEnum.LEGGACY.value]
            ):
                return True
        return False

#endregion

#region Contract getters

    def get_running_contract(self, guild_id: int, contract_id: str) -> Union[Dict, None]:
        if (doc := self.running_coops.find_one({"guild_id": guild_id, "contract_id": contract_id})) != None:
            return doc.copy()
        else:
            return None
    
    def get_all_contract_channel_ids(self, guild_id: int) -> Union[List[int], None]:
        if (cursor := self.running_coops.find({"guild_id": guild_id})) != None:
            return [contract["channel_id"] for contract in cursor]
        else:
            return None

    def get_nb_remaining(self, guild_id: int, contract_id: str) -> Union[int, None]:
        if (doc := self.running_coops.find_one({"guild_id": guild_id, "contract_id": contract_id})) != None:
            return len(doc["remaining"])
        else:
            return None

#endregion

#region Contract CRUD

    def create_contract_record(
        self,
        guild_id: int,
        contract_id: str,
        size: int,
        date: str,
        is_leggacy: bool,
        channel_id: int,
        remaining_ids: List[int],
        message_id: int = None,
        already_done_ids: List[int] = [],
        afk_ids: List[int] = []
    ):
        new_dic = {
            "guild_id": guild_id,
            "contract_id": contract_id,
            "size": size,
            "date": date,
            "is_leggacy": is_leggacy,
            "channel_id": channel_id,
            "message_id": message_id,
            "coops": [],
            "remaining": remaining_ids
        }
        if is_leggacy:
            new_dic["already_done"] = already_done_ids
        
        self.running_coops.insert_one(new_dic)
        
        participation = {}
        for id in remaining_ids:
            participation[str(id)] = ParticipationEnum.NO.value
        for id in already_done_ids:
            participation[str(id)] = ParticipationEnum.LEGGACY.value
        for id in afk_ids:
            participation[str(id)] = ParticipationEnum.AFK.value

        if self.participation_archive.find_one({"guild_id": guild_id, "contract_id": contract_id}) == None:
            self.participation_archive.insert_one({
                "guild_id": guild_id,
                "contract_id": contract_id,
                "data": {
                    date: {
                        "is_leggacy": is_leggacy,
                        "participation": participation
                    }
                }
            })
        else:
            self.participation_archive.update_one({"guild_id": guild_id, "contract_id": contract_id}, {"$set":
                {
                    f"data.{date}": {
                        "is_leggacy": is_leggacy,
                        "participation": participation
                    } 
                }
            })

    def remove_running_contract(self, guild_id: int, contract_id: str):
        self.running_coops.delete_one({"guild_id": guild_id, "contract_id": contract_id})

    def set_contract_message_id(self, guild_id: int, contract_id: str, message_id: int):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$set": {"message_id": message_id}}
        )

    def add_member_remaining(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$push": {"remaining": member_id}}
        )
    
    def add_member_already_done(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$push": {"already_done": member_id}}
        )
    
    def remove_member_remaining(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$pull": {"remaining": member_id}}
        )

    def remove_member_already_done(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$pull": {"already_done": member_id}}
        )

#endregion

#region Coop getters

    def get_nb_coops_created_by(self, guild_id: int, member_id: int) -> int:
        return self.running_coops.count_documents({
            "guild_id": guild_id,
            "coops": {
                "$elemMatch": {"creator": member_id, "completed_or_failed": CoopStatusEnum.RUNNING.value}
            }
        })

#endregion

#region Coop CRUD

    def create_coop_record(
        self,
        guild_id: int,
        contract_id: str,
        coop_code: str,
        creator_id: int,
        channel_id: int,
        locked: bool,
        grade: CoopGradeEnum,
        message_id: int = None
    ):
        new_dic = {
            "code": coop_code,
            "creator": creator_id,
            "grade": grade.value,
            "channel_id": channel_id,
            "message_id": message_id,
            "locked": locked,
            "completed_or_failed": CoopStatusEnum.RUNNING.value,
            "members": [creator_id]
        }
        
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$push": {"coops": new_dic}}
        )
    
    def set_coop_message_id(self, guild_id: int, contract_id: str, coop_nb: int, message_id: int):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$set": {f"coops.{coop_nb-1}.message_id": message_id}}
        )

    def set_coop_lock_status(self, guild_id: int, contract_id: str, coop_nb: int, locked: bool):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$set": {f"coops.{coop_nb-1}.locked": locked}}
        )

    def set_coop_running_status(self, guild_id: int, contract_id: str, coop_nb: int, status: CoopStatusEnum):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$set": {f"coops.{coop_nb-1}.completed_or_failed": status.value}}
        )

    def add_member_coop(self, guild_id: int, contract_id: str, coop_nb: int, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$push": {f"coops.{coop_nb-1}.members": member_id}}
        )

    def remove_member_coop(self, guild_id: int, contract_id: str, coop_nb: int, member_id: Union[int, str]):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$pull": {f"coops.{coop_nb-1}.members": member_id}}
        )

    def unset_coop_creator(self, guild_id: int, contract_id: str, coop_nb: int):
        self.running_coops.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id, f"coops.{coop_nb-1}": {"$exists": 1}},
            {"$set": {f"coops.{coop_nb-1}.creator": ""}}
        )

#endregion

#region Archive

    def get_contract_archive(self, guild_id: int, contract_id: str) -> Union[Dict, None]:
        return self.participation_archive.find_one({"guild_id": guild_id, "contract_id": contract_id})

    def get_archive_by_date(self, guild_id: int) -> Union[Dict, None]:
        date_dic = {}
        for doc in self.participation_archive.find({"guild_id": guild_id}):
            for date, occurrence in doc["data"].items():
                # If the contract occurrence is still running, ignore
                if self.running_coops.find_one({"guild_id": guild_id, "contract_id": doc["contract_id"], "date": date}) != None:
                    continue
                # Else
                if date not in date_dic.keys():
                    date_dic[date] = []
                value = occurrence.copy()
                value["contract_id"] = doc["contract_id"]
                date_dic[date].append(value)
        # Sorts by date
        date_dic = dict(sorted(date_dic.items(), reverse=True))
        return date_dic

    def set_member_participation(
        self,
        guild_id: int,
        contract_id: str,
        contract_date: str,
        member_id: Union[int, str],
        participation: ParticipationEnum
    ):
        self.participation_archive.find_one_and_update(
            {"guild_id": guild_id, "contract_id": contract_id},
            {"$set": {f"data.{contract_date}.participation.{member_id}": participation.value}}
        )

#endregion
