import discord as pycord
import interactions

import extensions.utils as utils

import json

#region Contract checks

def check_contract_channel(channel_id):
    """
    Returns the contract_id if channel is a contract channel,
    else returns False
    """
    running_coops = utils.read_json("running_coops")
    for contract_id, contract in running_coops.items():
        if contract["channel_id"] == channel_id:
            return contract_id
    return False

def check_context_menu_contract_message(target_message_id):
    """
    Returns the contract_id if target message is a contract message,
    else returns False
    """
    running_coops = utils.read_json("running_coops")
    for contract_id, contract in running_coops.items():
        if contract["message_id"] == target_message_id:
            return contract_id
    return False

#endregion

#region Coop checks

def check_coop_channel(channel_id):
    """
    Returns (contract_id, coop_nb) if channel is a coop channel,
    else returns False
    """
    running_coops = utils.read_json("running_coops")
    for contract_id, contract in running_coops.items():
        for i in range(len(contract["coops"])):
            if contract["coops"][i]["channel_id"] == channel_id:
                return contract_id, i+1
    return False

def check_context_menu_coop_message(target_message_id):
    """
    Returns (contract_id, coop_nb) if target message is a coop message,
    else returns False
    """
    running_coops = utils.read_json("running_coops")
    for contract_id, contract in running_coops.items():
        for i in range(len(contract["coops"])):
            if contract["coops"][i]["message_id"] == target_message_id:
                return contract_id, i+1
    return False

#endregion

#region Permissions checks

#endregion
