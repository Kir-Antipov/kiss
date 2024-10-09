# KISS

[![Build Status](https://img.shields.io/github/actions/workflow/status/Kir-Antipov/kiss/build.yml?logo=github)](https://github.com/Kir-Antipov/kiss/actions/workflows/build.yml)
[![Version](https://img.shields.io/github/v/release/Kir-Antipov/kiss?sort=date&label=version)](https://github.com/Kir-Antipov/kiss/releases/latest)
[![License](https://img.shields.io/github/license/Kir-Antipov/kiss?cacheSeconds=36000)](LICENSE.md)

`KISS`, aka "**Ki**r's **S**erver **S**oftware", is a template project designed for aspiring self-hosters.

When you want to self-host something, it often involves spinning up a few Docker containers here, setting up some CRON jobs there, configuring a reverse proxy, and adding a few quick-and-dirty shell scripts on top of all that for good measure. Usually, you either have to set everything up manually or write a Bash script to handle it for you. Either way, you'll likely run into management challenges when you want to migrate to a new server, remove an existing service, or add a new one. This is where this project comes in.

`KISS` is essentially a single shell script, `kiss.sh`, that lets you easily split your service definitions into separate sub-projects. It also simplifies essential but tedious tasks like installing dependencies, setting up CRON jobs, creating reverse proxies, managing SSL certificates, and more.

To get started, fork *(or just copy)* this repo, customize the `./services/` directory to your needs and liking, and you're good to go!

----

## License

Licensed under the terms of the [MIT License](LICENSE.md).
