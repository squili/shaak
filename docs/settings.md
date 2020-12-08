# Settings

## Settings
| Name          | Type    | Description
| :-            | :-      | :-
| prefix        | String  | The command prefix this server will use
| verbosity     | Boolean | Whether to print details of an error
| auth_role     | Role    | Specifies a role that can bypass all permissions checks on commands
| error_channel | Channel | Specifies a channel where uncaught errors will be sent to

## Commands
`settings.list`
:   Lists the current settings

`settings.set (name) [value]`
:   Sets the setting `name` to `value`  
    If no `value` is provided, returns the current value of the setting