### 2.7.3

- Filter out networking errors

### 2.7.2

- Add log for fallback embeds

### 2.7.1

- Remove deprecated item list handling

### 2.7.0

- Remove message scan queue

### 2.6.0

- Switch backing library to discord.py

### 2.5.1

- Add additional platform info to about command

### 2.5.0

- Add queue system to massbans

### 2.4.1

- Fix log channels being able to be set to be from other servers

### 2.4.0

- Add option to limit amount of guilds the bot can be in

### 2.3.5

- Fix guild cleanup task

### 2.3.4

- Fix clean shutdown

### 2.3.3

- Add scan timeout

### 2.3.2

- Log to file

### 2.3.1

- Fix previews permission checks

### 2.3.0

- Add setting to scan bot messages in word watch

### 2.2.1

- Fix incorrect permissions resolution

### 2.2.0

- Massban can now work off of files

### 2.1.1

- Fixed straggler icon url reference

### 2.1.0

- Added `stats` command

### 2.0.7

- Fixed ban utils reactions in threads

### 2.0.6

- Fixed reference to potentially null avatar asset

### 2.0.5

- Actually fixed guild icon url references

### 2.0.4

- Fixed thread support for message previews

### 2.0.3

- Fixed guild icon url references

### 2.0.2

- Fixed profile url references

### 2.0.1

- Automatically join new threads

### 2.0.0

- Switched to PyCord master
- Disabled voice states and prescences intents
- Fixed member cache flags
- Fixed ping datetime math
- Removed `begonecomments`

### 1.6.0

- Removed guild id from messages previews
- Removed when field from word watch logs

### 1.5.7

- Fixed `ww.unignore` not filtering by guild

### 1.5.6

- Increased guild data clearing grace period

### 1.5.5

- Fixed `ww.list` not displaying regex match types properly

### 1.5.4

- Renamed `ww.transfer` to `debug.transfer` to reflect it becoming a debug command

### 1.5.3

- Added `ww.transfer` command (undocumented)

### 1.5.2

- Fixed preview background errors
- Escaped background error backtraces

### 1.5.1

- Fixed `hl.role` errors
- Fixed `hl.add` adding spaces everywhere

### 1.5.0

- New migrations
- New docs
- Added `hotline` module

### 1.4.8

- Added `begonecomments` command to purge media channels of unwanted cringe

### 1.4.7

- Fixed action commands not properly checking permissions

### 1.4.6

- Notice: prior to this release, mass action commands had permissions improperly configured
- Mass action commands have been temporarily disabled

### 1.4.5

- New migrations
- New docs
- Added ban option to word watch

### 1.4.4

- Fixed error when reporting to a guild that has deleted their foreign channel

### 1.4.3

- Fixed invalid regex patterns cause modules to not properly initialize

### 1.4.2

- Added better logging

### 1.4.1

- Fixed previews showing the wrong guild

### 1.4.0

- Fixed `s` matching
- Fixed `str2bool` not properly handling booleans

### 1.4.0rc2

- Fixed `uw.cooldown` not updating the cooldown for cached entries
- Fixed `UnboundLocalError` when giving an invalid and valid id to `uw.watch`

### 1.4.0rc1

- New migrations
- New docs
- Added `uw.header` command
- Added `uw.list` command
- Made `uw.watch` and `uw.unwatch` accept multiple users at once

### 1.4.0rc0

- New migrations
- New docs
- Added `user_watch` module
- Cross-guild previews now show the source guild
- Fixed reasonless bans causing errors

### 1.3.2

- Fixed `AtrributeError` during subscriptions

### 1.3.1

- Added ignore cache
- Re-enabled regex match type
- Added debug command to get queue size

### 1.3.0

- New docs
- Added contains match type
- Added optional `s` to the end of word match
- Fixed prefix race condition
- Fixed match race condition
- Fixed forbidden reaction removal in list utility
- Fixed preview permissions check
- Depreciated regex match type

### 1.2.2

- Fix bad function naming causing massban to not trigger properly

### 1.2.1

- New docs
- Added massunban command

### 1.2.0

- Fixed race condition with message deletion and reaction additions causing errors to be thrown
- Cleaned up debug code in WordWatch

### 1.2.0rc5

- Stripped out legacy crossban code
- Crossbans should be marginally faster
- Updated invite message handling
- Fixed traceback code

### 1.2.0rc4

- Fixed `AttributeError` during ban forwarding
- Added traceback to background error logging

### 1.2.0rc3

- Fixed `NameError` during background error logging
- Made BanUtil invites delete after taking action

### 1.2.0rc2

- New migration
- New docs
- Restricted `massban` and `massrole` from executing in dms
- Added channel for logging background errors

### 1.2.0rc1

- Fixed an issue causing watch entries with an assigned ping group to not ping correctly

### 1.2.0rc0

- New migration
- New docs
- Added BanUtils invite messages with react buttons
- Added BanUtils subscibe/kick notifications
- Renamed `bu.bulk` to `massban`
- Added a more descriptive error message for `massban`
- Added `massrole`
- Finished documentation
- Cleaned up imports

### 1.1.8

- Allowed users to be ignored
- Message previews now show embeds
- Added permission checks to previews
- Added a message scan queue to prevent memory leakage under high demand

### 1.1.7

- Fixed some match type comparisons not using the enum values
- Fixed `ww.list` throwing `AttributeError`s when you tried using it without the shitty old cache

### 1.1.6

- Fixed an issue that caused the database to corrupt itself to try to remove nonexistant corruption

### 1.1.5

- Made sure that the database was completely wiped
- Fixed `ww.list_pings` not filtering by guild
- Stripped down word cache even further

### 1.1.4

- Made the bot delete everything on startup
- Fixed BanUtils not catching bans with no reason
- Fixed `WordWatchCache` `__hash__` function

### 1.1.3

- Added `Channel` and `Author` fields to the preview embed
- Moved watch's group id from cache to database

### 1.1.2

- Limited ban events to one per person
- Added mass ban command

### 1.1.1

- Fixed help command
- `ww.watch` with `ping.no` setting will remove ping group from an existing command

### 1.1.0

- Added docs
- Added `bot_docs` field to `product.json`

### 1.0.6

- New migration
- Added permission checks for `bu.subscribers` and `bu.subscriptions` commands
- Added `BanUtilBlock` model
- Added invite alerts
- Added guild invite alert blocks (`bu.block`, `bu.unblock`, `bu.blocks`)
- Added `receive_invite_alerts` column to `BanUtilSettings` model
- Added `bu.alert` command to set new setting column

### 1.0.5

- New migration
- Fixed close button not showing up on crossbans
- Fixed AttributeError for `bu.subscribers` and `bu.subscriptions` commands
- Case insensitive watches have their patterns set to lowercase. This helps with duplicate patterns. There's no migration for this, but it should slowly fix itself as time goes on.
- BU events now show user ids in the title
- BU events are now cleaned up after 30 days
- Crossban events now store their creation timestamp

### 1.0.4

- Created migrations
- Allowed more than one ban event to exist at any given time
- Update ban event based on outside factors
- Add close button

### 1.0.3

- Added GNU GPL 3 license
- Redid word watch's list output

### 1.0.2

- Added some debug prints to hope to catch the mystical error man (i think this is a regression?)
- Added more intents to hopefully cache more members
- Fixed module settings not being created properly on guild join
- Fixed a debug command crash
- Fixed a watch update crash

### 1.0.1

- Added debug commands
- Added `owner_id` field to settings

### 1.0.0

- Added BanUtils
- Switched database to tortoise-orm
