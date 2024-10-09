# Telegram Bot

[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FKir-Antipov%2Fkiss%2Fraw%2Fmaster%2Fservices%2Ftelegram-bot%2Fservice.json&query=version&label=version&color=blue)](https://github.com/Kir-Antipov/kiss/releases/latest)
[![License](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FKir-Antipov%2Fkiss%2Fraw%2Fmaster%2Fservices%2Ftelegram-bot%2Fservice.json&query=license&label=license&color=green)](../../LICENSE.md)

A custom Telegram bot designed to manage [`outline-server`](../outline-server/), providing an easy way to interact with and control your VPN through Telegram.

----

## Installation

First, you need to create two subdomains for your domain: `bot` and `tunnel`. The first one will be used to host a webhook for Telegram, and the latter will serve Shadowsocks configurations to authorized clients.

Next, install the service. Don't forget to provide your top-level domain to `KISS` using the `--domain` parameter.

After the installation process is complete, specify your bot's token, which can be requested from `@BotFather`, in the configuration file:

```bash
# {
#   "bot": {
#     "token": "<TOKEN>"
#   }
# }
nano /opt/telegram-bot/config.json
```

Then, restart the service with the following command:

```bash
docker restart telegram-bot
```

That's it! Everything should be up and running now.

----

## Usage

```
🧑‍💻 General Commands
/start - start the bot
/help - display this help page
/me - display your Telegram account info

🔐 VPN Management
/vpn - display your VPN access info
/vpn server - display VPN server details
/vpn server with <N> GB at <Port> as <Name> - update the server's data limit and name
/vpn add <User> with <N> GB for <N> weeks at <Port> as <Name> - issue a new access key
/vpn edit <User>:<ID> with <N> GB for <N> weeks as <Name> - modify an access key
/vpn remove <User>:<ID> - revoke an access key

👥 User Management
/user <User> - display information about a specific user
/users - display information about all registered users
/nickname <User> <Nickname> - set a nickname for a user

🛡️ Admin & Moderation
/op <User> - promote a user to admin
/deop <User> - demote an admin to a regular user
/ban <User> - ban a user
/pardon <User> - unban a user

🧹 Maintenance
/cleanup - manually run a cleanup
```

### Initial Setup

When the bot is first started, you won't have admin privileges. To get around that, send the bot its own token using the following command:

```
/ascend <TOKEN>
```

If the token matches the one associated with the bot, your ownership will be verified, and you will automatically be promoted to admin.

### User Management & Moderation

The bot allows you to refer to users either by their "nickname," which is *initially* set to their username and can be changed with the `/nickname` command, or by their Telegram ID.

To view information about a specific user, use the following command:

```
/user <User>
```

For a list of all registered users and their details, you can use:

```
/users
```

To set a new nickname for a specific user, use:

```
/nickname <User> <Nickname>
```

To promote a user to admin:

```
/op <User>
```

To demote an admin back to a regular user:

```
/deop <User>
```

To ban a user from ever using the bot again:

```
/ban <User>
```

To unban a previously banned user:

```
/pardon <User>
```

### VPN Management

The bot can manage your Outline Server and is designed to fully replace the Outline Manager app, while offering additional features like dynamic Shadowsocks configurations and automatic key prefixing.

To view your personal access key(s), send the following command to the bot:

```
/vpn
```

To get an overview of the VPN server, similar to the Outline Manager, use this command:

```
/vpn server
```

If you need to update the server's name, default port, or default data limit for access keys, you can add the necessary parameters to the previous command:

```
/vpn server [with <N> GB] [at <Port>] [as <Name>]
```

To issue a new access key, use this command:

```
/vpn add <User> [with <N> GB] [for <N> weeks] [at <Port>] [as <Name>]
```

The specified user will automatically receive a notification about the newly issued access key. If you don't want to associate the key with any specific user, you can use `_` instead.

To manually revoke an access key before its expiration date *(if it even has one)*, use the following command:

```
/vpn remove <User>[:<ID>]
```

If you omit the key's ID, the bot will automatically revoke all keys associated with the specified user.

----

## Backups

The service is configured to automatically back up itself daily outside of the `KISS` loop. The backups are located at `/opt/telegram-bot/backups`, and the latest backup is always symlinked to `/opt/telegram-bot/backups/latest.bak`.

To manually back up the service, execute the following command on your server:

```bash
telegram-bot-backup telegram-bot.bak
```

To restore the service from a previously backed-up state, use:

```bash
telegram-bot-restore telegram-bot.bak
```

----

## License

Licensed under the terms of the [MIT License](../../LICENSE.md).
