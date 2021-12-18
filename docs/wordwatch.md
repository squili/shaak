# Word Watch

## Concepts
### Watch Settings
Each watch has settings dictating how the bot search messages and the action it takes. Settings are set in the format of `name.value,name.value`. Settings of the `Boolean` type can be specified with just the setting name as shorthand.

| Name  | Type       | Default  | Description
| :-    | :-         | :-       | :-
| type  | String     | Required | Specifies what type of matching algorithm to use. The available options are `word`, `regex`, and `contains`.
| del   | Boolean    | No       | Whether to delete any message that the bot matches
| cased | Boolean    | No       | Whether to use case-sensitive matching. Not supported for the `word` type
| ping  | Ping Group | Null     | Which ping group (if any) to ping once a match is found. See [Ping Groups](wordwatch.md#ping-groups) for more information
| ban   | Integer    | Null     | Whether to ban the user. Supply a number for the days of message history to clear

### Ping Groups
Ping groups are lists of roles and users to be pinged once a match is found in a message. Each server can have as many ping groups and pings in the groups as they'd like

## Commands
`ww.watch (settings) (patterns)...`
:   Adds a watch with given [settings](wordwatch.md#watch-settings) and a list of patterns

`ww.list`
:   Lists your word watch entires

`ww.clear_watches`
:   Clears all the watches you have    

`ww.remove (entries)...`
:   Removes the specified entries. You can either use numbers or ranges of numbers (eg. `3-7`). Use `ww.list` to get a watch's number

`ww.qremove (patterns)...`
:   Searches for watches with the same pattern as the one specified and deletes it

`ww.ignore (references)...`
:   Adds either a user, channel, or role to the ignore list. Messages which fit the ignore list aren't scanned by Word Watch

`ww.ignored`
:   Lists ignored items for this guild

`ww.unignore (references)...`
:   Removes either a user, channel, or role from the ignore list

`ww.log [channel]`
:   Sets the log channel. Call with no channel to see the current channel, and either `clear`, `reset`, or `disable` to disable logging

`ww.header [header]`
:   Sets the log header. Call with no text to see the current header, and either `clear`, `reset`, or `disable` to disable the header

`ww.add_ping (group_name) (pings)...`
:   Adds listed pings to the target group. If the group doesn't exist, create it

`ww.remove_ping (group_name) (pings)...`
:   Removes listed ping from the target group

`ww.delete_group (group_name)`
:   Take a guess

`ww.list_groups`
:   Lists this server's groups

`ww.list_pings (group_name)`
:   Lists the specified group's pings

`ww.scan_bots [selected]`
:   Sets whether to scan bots. Call with nothing to see the current value, and either `on`, `yes`, or `enable` to turn it on (and anything else to turn it off)