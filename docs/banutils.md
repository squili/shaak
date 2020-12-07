# Ban Utils

## Concepts
### Ban events
Ban events are created once a ban is detected. Once they are created, they are put into your server's domestic events channel. From there, you can press the reaction buttons to take action
### Subscriptions
One server can invite another server to it's crossban feed. If it's not blocked or disabled, an invite will be sent to the target server's foreign events channel. If the invite is acted upon, either by pressing the button or using `bu.subscribe`, a notification will be sent to the server notifying it that a new server is subscribed to it's crossban feed. From there, every crossban report will go to that server's foreign events channel
### Crossbans
Once a ban event is reported, a crossban will be created for each subscribed server. This crossban can be forwarded or seconded from the reaction buttons

## Commands
`bu.invite (server_id)`
:   Invites a server to your crossban feed

`bu.subscribe (server_id)`
:   Accepts a server's invite

`bu.unsubscribe (server_id)`
:   Unsubscribes from a server

`bu.kick (server_id)`
:   Kicks a server from your crossban feed. Deletes any pending invites found

`bu.foreign (channel)`
:   Sets a channel as your foreign events channel

`bu.domestic (channel)`
:   Sets a channel as your domestic events channel

`bu.subscribers`
:   Lists a server's subscribers

`bu.subscriptions`
:   Lists a server's subscriptions

`bu.block (server_id)`
:   Blocks a server from sending you invite requests

`bu.unblock (server_id)`
:   Unblocks a server from sending you invite requests

`bu.blocked`
:   Lists blocked servers

`bu.alerts [toggle]`
:   Sets whether to send invite alerts. Provide no arguments to get current value
