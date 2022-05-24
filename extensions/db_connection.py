from pymongo import MongoClient

from extensions.enums import ParticipationEnum, CoopStatusEnum

from typing import *

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
        if (doc := self.guild_config.find_one({"guild_id": guild_id})) and key in doc.keys():
            return doc[key]
        else:
            return None

    def set_guild_config_value(self, guild_id: int, key: str, value):
        self.guild_config.update_one({"guild_id": guild_id}, {"$set": {key: value}})

#endregion

#region Alt index

    # OK
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

    # OK
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
            return doc["data"][member_id]["main"]
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
            return doc["data"][member_id]["alt"]
        else:
            return None

#endregion

#region Contract checks

    def is_contract_running(self, guild_id: int, contract_id: str) -> Union[bool, None]:
        if (doc := self.running_coops.find_one({"guild_id": guild_id})):
            return contract_id in doc["data"].keys()
        else:
            return None
    
    def is_contract_in_archive(self, guild_id: int, contract_id: str) -> Union[bool, None]:
        if (doc := self.participation_archive.find_one({"guild_id": guild_id})):
            return contract_id in doc["data"].keys()
        else:
            return None
    
    def has_member_participated_in_previous_contract(self, guild_id: int, contract_id: str, member_id: int) -> Union[bool, None]:
        if (doc := self.participation_archive.find_one({"guild_id": guild_id})) and contract_id not in doc["data"].keys():
            return None
        for contract in doc["data"][contract_id].values():
            if (
                str(member_id) in contract["participation"].keys()
                and contract["participation"][str(member_id)] in [ParticipationEnum.YES.value, ParticipationEnum.LEGGACY.value]
            ):
                return True
        return False

#endregion

#region Contract getters

    def get_running_dic(self, guild_id: int) -> Union[Dict, None]:
        if (doc := self.running_coops.find_one({"guild_id": guild_id})) != None:
            return doc["data"].copy()
        else:
            return None

    def get_contract_data(self, guild_id: int, contract_id: str) -> Union[Dict, None]:
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            return doc["data"][contract_id].copy()
        else:
            return None
    
    def get_all_contract_channel_ids(self, guild_id: int) -> Union[List[int], None]:
        if (doc := self.running_coops.find_one({"guild_id": guild_id})) != None:
            return [contract["channel_id"] for contract in doc["data"].values()]
        else:
            return None

    def get_nb_remaining(self, guild_id: int, contract_id: str) -> Union[int, None]:
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            return len(doc["data"][contract_id]["remaining"])
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
        
        self.running_coops.update_one({"guild_id": guild_id}, {"$set":
            {
                f"data.{contract_id}": new_dic
            }
        })

        if self.participation_archive.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        ) == None:
            self.participation_archive.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}": {} 
                }
            })
        
        participation = {}
        for id in remaining_ids:
            participation[str(id)] = ParticipationEnum.NO.value
        for id in already_done_ids:
            participation[str(id)] = ParticipationEnum.LEGGACY.value
        for id in afk_ids:
            participation[str(id)] = ParticipationEnum.AFK.value
        self.participation_archive.update_one({"guild_id": guild_id}, {"$set":
            {
                f"data.{contract_id}.{date}": {
                    "is_leggacy": is_leggacy,
                    "participation": participation
                } 
            }
        })

    def remove_running_contract(self, guild_id: int, contract_id: str):
        self.running_coops.update_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            },
            { "$unset": {f"data.{contract_id}": ""}}
        )

    def set_contract_message_id(self, guild_id: int, contract_id: str, message_id: int):
        if self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        ) != None:
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.message_id": message_id
                }
            })

    def add_member_remaining(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            remaining = doc["data"][contract_id]["remaining"]
            remaining.append(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.remaining": remaining
                }
            })
    
    def add_member_already_done(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            done = doc["data"][contract_id]["already_done"]
            done.append(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.already_done": done
                }
            })
    
    def remove_member_remaining(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            remaining = doc["data"][contract_id]["remaining"]
            remaining.remove(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.remaining": remaining
                }
            })

    def remove_member_already_done(self, guild_id: int, contract_id: str, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )) != None:
            done = doc["data"][contract_id]["already_done"]
            done.remove(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.already_done": done
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
        message_id: int = None
    ):
        new_dic = {
            "code": coop_code,
            "creator": creator_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "locked": locked,
            "completed_or_failed": CoopStatusEnum.RUNNING.value,
            "members": [creator_id]
        }

        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )):
            coop_list = doc["data"][contract_id]["coops"].copy()
            coop_list.append(new_dic)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops": coop_list
                }
            })
    
    def set_coop_message_id(self, guild_id: int, contract_id: str, coop_nb: int, message_id: int):
        if self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        ) != None:
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.message_id": message_id
                }
            })

    def set_coop_lock_status(self, guild_id: int, contract_id: str, coop_nb: int, locked: bool):
        if self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        ) != None:
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.locked": locked
                }
            })

    def set_coop_running_status(self, guild_id: int, contract_id: str, coop_nb: int, status: CoopStatusEnum):
        if self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        ) != None:
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.completed_or_failed": status.value
                }
            })

    def add_member_coop(self, guild_id: int, contract_id: str, coop_nb: int, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        )) != None:
            members = doc["data"][contract_id]["coops"][coop_nb-1]["members"]
            members.append(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.members": members
                }
            })

    def remove_member_coop(self, guild_id: int, contract_id: str, coop_nb: int, member_id: Union[int, str]):
        if (doc := self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        )) != None:
            members = doc["data"][contract_id]["coops"][coop_nb-1]["members"]
            members.remove(member_id)
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.members": members
                }
            })

    def unset_coop_creator(self, guild_id: int, contract_id: str, coop_nb: int):
        if self.running_coops.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.coops.{coop_nb-1}": {
                    "$exists": 1
                }
            }
        ) != None:
            self.running_coops.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.coops.{coop_nb-1}.creator": ""
                }
            })

#endregion

#region Archive

    def get_contract_archive(self, guild_id: int, contract_id: str) -> Union[Dict, None]:
        if (doc := self.participation_archive.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}": {
                    "$exists": 1
                }
            }
        )):
            return doc["data"][contract_id].copy()
        else:
            return None

    def get_archive_by_date(self, guild_id: int) -> Union[Dict, None]:
        if (
            (running := self.running_coops.find_one({"guild_id": guild_id})) != None
            and (archive := self.participation_archive.find_one({"guild_id": guild_id})) != None
        ): 
            date_dic = {}
            for id, occurrences in archive["data"].items():
                for date, occurrence in occurrences.items():
                    # If the contract occurrence is still running, ignore
                    if id in running["data"].keys() and date == running["data"][id]["date"]:
                        continue
                    # Else
                    if date not in date_dic.keys():
                        date_dic[date] = []
                    value = occurrence.copy()
                    value["contract_id"] = id
                    date_dic[date].append(value)
            # Sorts by date
            date_dic = dict(sorted(date_dic.items(), reverse=True))
            return date_dic
        else:
            return None

    # OK
    def set_member_participation(
        self,
        guild_id: int,
        contract_id: str,
        contract_date: str,
        member_id: Union[int, str],
        participation: ParticipationEnum
    ):
        if self.participation_archive.find_one(
            {
                "guild_id": guild_id,
                f"data.{contract_id}.{contract_date}": {
                    "$exists": 1
                }
            }
        ):
            self.participation_archive.update_one({"guild_id": guild_id}, {"$set":
                {
                    f"data.{contract_id}.{contract_date}.participation.{member_id}": participation.value
                }
            })

#endregion