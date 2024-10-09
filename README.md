# KISS

[![Build Status](https://img.shields.io/github/actions/workflow/status/Kir-Antipov/kiss/build.yml?logo=github)](https://github.com/Kir-Antipov/kiss/actions/workflows/build.yml)
[![Version](https://img.shields.io/github/v/release/Kir-Antipov/kiss?sort=date&label=version)](https://github.com/Kir-Antipov/kiss/releases/latest)
[![License](https://img.shields.io/github/license/Kir-Antipov/kiss?cacheSeconds=36000)](LICENSE.md)

<img alt="KISS Icon" src="media/icon.png" width="128">

`KISS`, aka "**Ki**r's **S**erver **S**oftware", is a template project designed for aspiring self-hosters.

When you want to self-host something, it often involves spinning up a few Docker containers here, setting up some CRON jobs there, configuring a reverse proxy, and adding a few quick-and-dirty shell scripts on top of all that for good measure. Usually, you either have to set everything up manually or write a Bash script to handle it for you. Either way, you'll likely run into management challenges when you want to migrate to a new server, remove an existing service, or add a new one. This is where this project comes in.

`KISS` is essentially a single shell script, `kiss.sh`, that lets you easily split your service definitions into separate sub-projects. It also simplifies essential but tedious tasks like installing dependencies, setting up CRON jobs, creating reverse proxies, managing SSL certificates, and more.

To get started, fork *(or just copy)* this repo, customize the `./services/` directory to your needs and liking, and you're good to go!

---

## Usage

```
Usage: kiss <command> [<options>] [<file>]
       kiss ssh [-i <file>] <destination> <command> [<options>] [<file>]

Manage the deployment, backup, and recovery routines for the server software.

Examples:
  kiss build -o ./build/kiss
  kiss install
  kiss backup -o backup.tar.gz
  kiss restore backup.tar.gz
  kiss ssh -i ~/.ssh/id_rsa root@42.42.42.42 recreate backup.tar.gz

Commands:
  build [-o <build>]         Build enabled services into a single executable
  install                    Install built services
  uninstall                  Uninstall built services
  backup [-o <backup>]       Backup each service via the "backup" command
  restore <backup>           Restore the state of services from a backup
  recreate <backup>          Install built services and then restore their state
  <command>                  Execute the specified <command> for each service

Options:
  -h, --help                 Display this help text and exit
  -v, --version              Display version information and exit
  -q, --quiet                Suppress all normal output
  -e, --email                Specify the ACME email address
  -d, --domain               Specify the domain name of the current machine
  -o, --output <file>        Write output to <file>
  -i, --identity <file>      Select the <file> from which the identity is read
```

### Build

Once you're done configuring your services *(more on that later)*, it's time to package everything into a single file that can be distributed to the target server. To do this, use the `build` command and optionally provide `kiss.sh` with an output filename for the resulting executable:

```bash
./kiss.sh build -o ./kiss
```

If the build process completes successfully, you can find the executable representing the current state of the repo at the specified location *(or `./build/kiss` if you didn't specify one)* and move on to the next step.

### Install

After building `KISS`, it can be distributed to the server where you'd like to install the configured services. Then, run:

```bash
./kiss install --domain "my-domain.if-any.net" --email "acme-email@if-any.net"
```

Congratulations! All the services should now be up and running.

Note: You only need to specify the domain name using the `--domain` parameter if at least one of the configured services requires it. The same applies to the optional `--email` parameter - only use it if one of your services needs an SSL certificate **and** you want to receive notifications when it's about to expire or if any other issue arises.

### Uninstall

If you need to uninstall the configured services, run the following command on your server:

```bash
./kiss uninstall --domain "my-domain.if-any.net"
```

Note: You only need to provide the domain name via the `--domain` parameter if you specified it during installation.

### Backup

`KISS` provides a simple way to create a combined backup for all your services. To do this, run the following command on your server:

```bash
./kiss backup --output "my-backup.tar.gz"
```

The backup file will be saved to the specified location. This file can then be used as input for the `restore` command.

### Restore

If you need to restore your services to a previously backed-up state, run the following command on your server:

```bash
./kiss restore "my-backup.tar.gz"
```

### SSH Mode

`KISS` can run itself on a remote server by using the special `ssh` command, which can be combined with the regular commands listed above. This means you don't have to worry about manually uploading it and its dependent files to a server, running it, or cleaning up afterward - `KISS` will handle all of that for you, including uploading and downloading input and output files as needed. Here are some examples:

```bash
./kiss ssh -i ~/.ssh/id_rsa root@42.42.42.42 install -d "my-domain.if-any.net" -e "acme-email@if-any.net"
./kiss ssh -i ~/.ssh/id_rsa root@42.42.42.42 backup -o "backup.tar.gz"
./kiss ssh -i ~/.ssh/id_rsa root@42.42.42.42 restore "backup.tar.gz"
./kiss ssh -i ~/.ssh/id_rsa root@42.42.42.42 uninstall -d "my-domain.if-any.net"
```

----

## File Structure

The repository follows a pretty simple file structure to keep things clean and easy to manage:

```bash
# Contains reusable shell script files that provide
# shared functionality for your services.
libs/
  <library-name>.sh

# Each subdirectory represents a managed service,
# with its configuration and scripts stored inside.
services/
  <service-name>/
    ...
    service.json

# The main script that manages the build, installation,
# and operation of your services.
kiss.sh
```

----

## Services

Each service should have its own directory in `./services/` with a `service.json` file at its root.

### `service.json`

The `service.json` file is a metadata file required by `KISS`, which provides information about how the service should be handled. For those familiar with Node.js' [`package.json`](https://docs.npmjs.com/cli/v10/configuring-npm/package-json), `service.json` follows a similar structure, so you'll likely find it pretty intuitive.

Let's walk through the most important fields:

#### `name`

A URI-friendly name for the service.

```json
"name": "foo"
```

#### `version`

A [SemVer](https://semver.org/)-compliant version of the service.

```json
"version": "1.0.0"
```

#### `scripts`

A dictionary of script commands that are run at various points in the service's lifecycle. The key is the lifecycle event, and the value is the command to execute at that stage.

To integrate with `KISS`, your service may implement the following commands:
- `build` - if your service requires additional steps before `KISS` is built.
- `install` - for custom installation logic not covered by `service.json`.
- `uninstall` - for custom uninstall logic.
- `backup <output-filename>` - to create a backup of your service.
- `restore <input-filename>` - to restore your service from a backup.

```json
"scripts": {
  "build": "./build.sh",
  "preinstall": "echo Starting the installation...",
  "install": "./install.sh",
  "postinstall": "echo Finished the installation.",
  "uninstall": "./uninstall.sh",
  "backup": "./backup.sh \"$1\"",
  "restore": "./restore.sh \"$1\""
}
```

#### `files`

A dictionary that specifies the files to be copied to the target machine during service installation. The key is the filename *(relative to the service's root)*, and the value is the destination path on the target machine. You can also specify file permissions *(as in `chmod`)*, which default to `rwxr-xr-x` if not provided.

Note: You can freely source other shell scripts from those listed in `files`, and `KISS` will handle this scenario for you.

```json
"files": {
  "backup.sh": "/usr/local/bin/foo-backup",
  "restore.sh": ["/usr/local/bin/foo-restore", "rwxr-xr-x"]
}
```

#### `jobs`

A dictionary defining CRON jobs to be set up during service installation. The key is the job command, and the value is the CRON schedule.

```json
"jobs": {
  "/usr/local/bin/foo-backup": "0 0 * * *"
}
```

#### `proxies`

A dictionary for defining reverse proxies that should be set up when the service is installed. The key is the publicly accessible server URI, and the value is the backend service URI to redirect requests to.

- The server URI defaults to `https://`, and the backend URI defaults to `http://` if the protocol is omitted.
- If your server uses `https://`, `KISS` will automatically fetch SSL certificates from [Let's Encrypt](https://letsencrypt.org/).
- You can use `*` in place of the domain name. For server URIs, `KISS` will replace `*` with the domain specified via the `--domain` parameter, while for backend URIs, `*` typically resolves to `localhost`.

```json
"proxies": {
  "foo.*": "*:1234",
  "http://bar.*": "*:1235"
}
```

#### `dependencies`

An array of system packages that should be installed when the service is being installed.

```json
"dependencies": [
  "docker",
  "jq"
]
```

#### `devDependencies`

An array of system packages that should be installed when the service is being built.

```json
"devDependencies": [
  "docker",
  "jq"
]
```

### Preconfigured Services

This template comes with a few preconfigured services to showcase how `KISS` works. These examples can be used as-is or customized for your own needs:

 - **`certbot`**: A service that automates the renewal of SSL certificates using the [EFF's Certbot](https://certbot.eff.org/) tool.

 - **`outline-server`**: A self-hosted VPN server designed to provide secure internet access. With [Outline](https://github.com/Jigsaw-Code/outline-server), you can easily manage your own VPN, allowing users to enjoy encrypted communication and bypass censorship and/or geo-restrictions.

 - **`telegram-bot`**: A custom Telegram bot designed to manage the Outline Server, providing an easy way to interact with and control your VPN through Telegram. While it's built with `outline-server` in mind, this bot is fully extensible, so you can modify it to handle any task you want.

 - **`watchtower`**: A lightweight service that automatically updates your Docker containers. [Watchtower](https://github.com/containrrr/watchtower/) monitors your running Docker services and, if a new version of a container image is available, it will seamlessly pull the update and restart the service for you.

----

## GitHub Workflows

In addition to the standard CI jobs that facilitate the maintenance of the project by automatically building `KISS` whenever you push a new commit or create a new release, this repository includes a few additional workflows: `install`, `reinstall`, and `backup`. These jobs are designed to help you deploy your `KISS` instance directly to your server via SSH, and even maintain backups of your services!

To enable these workflows, you need to configure the following secrets and variables:

| Name | Type | Default | Description |
|------|:----:|:-------:|-------------|
| `KISS_DOMAIN` | Secret | N/A | The domain name associated with the remote server. |
| `KISS_EMAIL` | Secret | *(none)* | The email address registered for ACME services. |
| `SSH_USER` | Secret | `root` | The username used to log into the remote server via SSH. This should have appropriate privileges to install or manage services. |
| `SSH_HOST` | Secret | N/A | The IP address or domain of the remote server where the `KISS` instance and its services will be deployed or managed. |
| `SSH_PRIVATE_KEY` | Secret | N/A | The private SSH key used to authenticate with the remote server. This key allows secure, passwordless login when paired with the corresponding public key on the server. |
| `BACKUP_KEY` | Secret | N/A | A key used to encrypt backups. This ensures that backups created by the system are securely encrypted before being stored or transferred. |
| `BACKUP_RETENTION_DAYS` | Variable | `90` | The number of days to retain the backups. After this period, older backups will be automatically deleted. |

With this information in place, `KISS` will be able to install or reinstall your services on the specified server whenever you dispatch `install` or `reinstall` jobs, respectively. Additionally, it will begin creating automated encrypted backups of your services through scheduled *(or manual)* dispatches of the `backup` job.

----

## License

Licensed under the terms of the [MIT License](LICENSE.md).
