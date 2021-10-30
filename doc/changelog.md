# v1.3.4

**Changes:**

- Improved admin command to modify data files
- Clicking a second time on the already done button puts you back in remaining, unless it says in the bot's archive you have indeed done the contratc before
- Improved contract message readability
- Added a 10s timeout to wait_for_component events
- Allowing for admins to kick even when the coop is completed (when someone doesn't join the in-game coop)

**Bugfixes:**

- Fixed interfering button events when multiple wait_for_component are waiting at the same time

# v1.3.3

**Changes:**

- Removed useless contract ID in join message
"you gotta idiot proof HARD for me, man" -DrJon

# v1.3.2

**Bugfixes:**

- Fixed the participation count for AFK role. It now ignores contract occurrences which are still running

# v1.3.1

**Bugfixes:**

- Fixed the value type on the owner's command to modify JSON files
- Fix: manage coop creator role when someone is creator of multiple coops at the same time

# v1.3.0

**New features:**

- New commands reserved for the bot owner to be able to retrieve and modify the JSON data files remotely
- Added setting to keep the coop channel after the coop is marked completed or failed
- Added setting to be able not to use embeds, since mentions within embeds don't work on mobile if the user is not in cache
- Added slash command alternatives to context menus, since they don't exist on mobile

**Bugfixes:**

- Fixed an issue where some roles could have unintended write messages permission in the contract channels
- Fixed the color of the coop button which you stay green when the coop is locked at creation

# v1.2.2

**Changes:**

- Added changelog file in source

**Bugfixes:**

- Commands now properly manage users who left the guild

# v1.2.1

**Changes:**

- Contract channel permissions are now copied and modified from the bot commands channel
- Added guest role setting: the guest is completely ignored for coops

# v1.2.0

**New features:**

- The number of coops to miss before being made AFK is now a variable per guild
- Settings command: the only settings available for change is COOPS_BEFORE_AFK for now

**Bugfixes:**

- Replaced the incorrect "&help" in the bot's activity message by "/help"
- Fixed a bug where channel permissions for the bot were given to the role named "Chicken3PO" only, disregarding possible application name changes such as with the dev app "[Dev] Chicken3PO"

# v1.1.0

**New features:**

- At coop creation, creates a private coop channel
- Role to have access to the coop channel
- Deletes role and channel when coop is completed or failed

# v1.0.0

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