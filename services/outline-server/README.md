# Outline Server

[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FKir-Antipov%2Fkiss%2Fraw%2Fmaster%2Fservices%2Foutline-server%2Fservice.json&query=version&label=version&color=blue)](https://github.com/Kir-Antipov/kiss/releases/latest)
[![License](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FKir-Antipov%2Fkiss%2Fraw%2Fmaster%2Fservices%2Foutline-server%2Fservice.json&query=license&label=license&color=green)](../../LICENSE.md)

A self-hosted VPN server designed to provide secure internet access. With [Outline](https://github.com/Jigsaw-Code/outline-server), you can easily manage your own VPN, allowing users to enjoy encrypted communication and bypass censorship and/or geo-restrictions.

----

## Usage

The service is intended to be controlled by [`telegram-bot`](../telegram-bot).

However, if you need or want to use the [Outline Manager](https://getoutline.org/) app as usual, run the following command on your server:

```bash
jq -csR './"\n"|map(./":"|{key:.[0],value:.[1:]|join(":")}|select(.key))|from_entries' /opt/outline/access.txt
```

Then, copy the output into **Step 2** of the **Set up Outline anywhere** interface.

----

## Backups

The service is configured to automatically back up itself daily outside of the `KISS` loop. The backups are located at `/opt/outline/backups`, and the latest backup is always symlinked to `/opt/outline/backups/latest.bak`.

To manually back up the service, execute the following command on your server:

```bash
outline-server-backup outline.bak
```

To restore the service from a previously backed-up state, use:

```bash
outline-server-restore outline.bak
```

----

## License

Licensed under the terms of the [MIT License](../../LICENSE.md).
