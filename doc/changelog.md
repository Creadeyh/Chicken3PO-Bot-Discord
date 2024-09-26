# Changelog

## v2.1.1

**Backend changes:**

- Database connection object is now a singleton
- Added log to all database connection exception to debug server issue
- Automatically kill the bot process if it can't connect to the database (bot to be restarted by the server)
- Removed BOT_VERSION from config.json
- Deleted leftover data folder

## v2.1.0

**New features:**

- Added a grade option when creating a coop, so your teammates know which grade is the coop in

**Changes:**

- Because of the new possibility to replay leggacy contracts for points in EggInc, you can now remove yourself from the Already done list at any point, even if you have completed it in an earlier instance

**Backend changes:**

- Updated discord-py-interactions from 4.3.1 to 4.4.0
- Added requirements.txt for dependency listing

## v2.0.1

**Changes:**

- Removed mention of already done AFK members when a leggacy contract is added, to avoid this mild annoyance to AFK members

## v2.0.0

**Changes:**

- Slash commands related to a specific contract now have to be typed in the targeted contract channel
- Slash commands related to a specific coop now have to be typed in the targeted coop channel
- Dropped support for coop messages in embeds
- Automatically deletes user-sent messages in contract channels, only authorizing slash commands and messages from bot
- Improved the help command

**Backend changes:**

- Switched Discord library from discord.py & discord-interactions v3 to pycord v2 & discord-interactions v4
- Code files re-organization
- Factorized the view update for contract and coop messages
- Common permission checks
- Switched data storage from JSON files to MongoDB database

**Bugfixes:**

- Fixed the state of the coop join button which didn't stay as completed after kicking a member

## v1.3.7.1

**Backend changes:**

- Config fix for version 2

## v1.3.7

**Backend changes:**

- Config preparation for version 2

## v1.3.6

**Bugfixes:**

- Fixed the state of the coop join button after kicking someone from a full coop
- Fixed the multiple pings to Coop Organizer when remaining list is empty and AFK joins
- Fixed the AFK role attribution: doesn't give it back if player has just joined a running coop
- On setup, now asking to move the Coop Organizer, Coop Creator, AFK and Alt roles below the bot role if they already exist

## v1.3.5

**Bugfixes:**

- Fixed issue where main account of somebody with an alt could not be kicked out of a coop

## v1.3.4

**Changes:**

- Improved admin command to modify data files
- Clicking a second time on the already done button puts you back in remaining, unless it says in the bot's archive you have indeed done the contract before
- Improved contract message readability
- Added a 10s timeout to wait_for_component events
- Allowing for admins to kick even when the coop is completed (when someone doesn't join the in-game coop)

**Bugfixes:**

- Fixed interfering button events when multiple wait_for_component are waiting at the same time

## v1.3.3

**Changes:**

- Removed useless contract ID in join message
"you gotta idiot proof HARD for me, man" -DrJon

## v1.3.2

**Bugfixes:**

- Fixed the participation count for AFK role. It now ignores contract occurrences which are still running

## v1.3.1

**Bugfixes:**

- Fixed the value type on the owner's command to modify JSON files
- Fix: manage coop creator role when someone is creator of multiple coops at the same time

## v1.3.0

**New features:**

- New commands reserved for the bot owner to be able to retrieve and modify the JSON data files remotely
- Added setting to keep the coop channel after the coop is marked completed or failed
- Added setting to be able not to use embeds, since mentions within embeds don't work on mobile if the user is not in cache
- Added slash command alternatives to context menus, since they don't exist on mobile

**Bugfixes:**

- Fixed an issue where some roles could have unintended write messages permission in the contract channels
- Fixed the color of the coop button which you stay green when the coop is locked at creation

## v1.2.2

**Changes:**

- Added changelog file in source

**Bugfixes:**

- Commands now properly manage users who left the guild

## v1.2.1

**Changes:**

- Contract channel permissions are now copied and modified from the bot commands channel
- Added guest role setting: the guest is completely ignored for coops

## v1.2.0

**New features:**

- The number of coops to miss before being made AFK is now a variable per guild
- Settings command: the only settings available for change is COOPS_BEFORE_AFK for now

**Bugfixes:**

- Replaced the incorrect "&help" in the bot's activity message by "/help"
- Fixed a bug where channel permissions for the bot were given to the role named "Chicken3PO" only, disregarding possible application name changes such as with the dev app "[Dev] Chicken3PO"

## v1.1.0

**New features:**

- At coop creation, creates a private coop channel
- Role to have access to the coop channel
- Deletes role and channel when coop is completed or failed

## v1.0.0

**Features:**

- Setup command channel and roles (coop organizer, coop creator, afk, alt)
- New contract slash command
- New coop slash command
- Ping to coop organizers when the remaining list is empty
- Coop kick slash command
- Coop codes slash command
- Coop lock slash command
- Coop unlock slash command
- Coop completed context menu
- Coop failed context menu
- Remove contract context menu
- Alt account register slash command
- Alt account unregister slash command
- Join coop button
- Already done leggacy button
- Help slash command
