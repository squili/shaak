# User Watch

## Commands
`uw.log [channel]`
:   Sets the log channel. Call with no channel to see the current channel, and either `clear`, `reset`, or `disable` to disable logging

`uw.cooldown [cooldown]`
:   Sets the cooldown between logged messages. Call with no cooldown to see the current cooldown, and either `clear`, `reset`, or `disable` to reset the value to default (15 minutes)

`uw.watch (user)`
:   Adds a user to the watch. Will send an alert to the log channel when this user talks

`uw.unwatch (user)`
:   Removes a user from the watch

`uw.header [header]`
:   Sets the log header. Call with no text to see the current header, and either `clear`, `reset`, or `disable` to disable the header

`uw.list`
:   Lists your current user watch entries