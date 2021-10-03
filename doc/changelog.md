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