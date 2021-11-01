The bot allows you to manage [Transmission server](https://transmissionbt.com/) from Telegram chat (add torrents, list running downloads, etc.)

## Prerequisites
- create bot user via [BotFather and get API token](https://core.telegram.org/bots#3-how-do-i-create-a-bot);
- you have to setup Transmission server on your own (this bot doesn't cover the setup of the server part);
- Docker.

### Optional functionality
The bot is able to trigger a deployment in Terraform cloud and fetch the value of Terraform output variable that store IP address of a host that runs Transmission server (currently it expects only 1 output variable so there is no logic to choose the right variable if there are several of them).

The bot will try to reach Terraform cloud it if you don't provide a value for `TRANSMISSION_HOST`.

## Run the bot in Docker container
### Environment variables
Before you run the container, you need to prepare several environment variables:

| Variable                  | Description                                                                     | Default               |
| ------------------------- | ------------------------------------------------------------------------------- | --------------------- |
| TELEGRAM_BOT_TOKEN        | API token that BotFather gives you when you create a bot                        | -                     |
| TRANSMISSION_HOST         | IP address of a server with Transmission                                        | -                     |
| TRANSMISSION_PORT         | Port of Transmission server                                                     | 9091                  |
| TRANSMISSION_USER         | Transmission user                                                               | transmission          |
| TRANSMISSION_PASSWORD     | Password of Transmission user                                                   | transmission          |
| TRANSMISSION_DOWNLOAD_DIR | Path to a folder where transmission will download files                         | /tmp/downloads        |
| AUTHORIZED_USERS          | Comma-separated IDs of Telegram users that are allowed to interact with the bot | '294967926,191151492' |

Partially optional variables (they are ignored if you set `TRANSMISSION_HOST`)

| Variable          | Description                            | Default |
| ----------------- | -------------------------------------- | ------- |
| WORKSPACE_ID      | ID of Terraform cloud workspace        | -       |
| WORKSPACE_NAME    | Name of Terraform cloud workspace      | -       |
| ORGANIZATION_NAME | Name of Terraform cloud organization   | -       |
| TF_CLOUD_TOKEN    | Token to access API of Terraform cloud | -       |

### Build Docker image
```sh
$ docker build -t transmission_mgmt_bot_image .
```
#### Building the image on Raspberry PI
You will probably get following error when you build the image on Raspberry Pi:
```
Step 4/6 : RUN pip install -r requirements.txt
 ---> Running in dbffcfcbfa54
Fatal Python error: pyinit_main: can't initialize time
Python runtime state: core initialized
PermissionError: [Errno 1] Operation not permitted

Current thread 0xb6f0d010 (most recent call first):
<no Python frame>
The command '/bin/sh -c pip install -r requirements.txt' returned a non-zero code: 1
```

You need to install libseccomp2 >=2.4.3-1. It is currently not available for Raspberry PI OS, but can be installed from the Buster Backports repo:
```
# Get signing keys to verify the new packages, otherwise they will not install
$ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 04EE7237B7D453EC 648ACFD622F3D138

# Add the Buster backport repository to apt sources.list
$ echo 'deb http://httpredir.debian.org/debian buster-backports main contrib non-free' | sudo tee -a /etc/apt/sources.list.d/debian-backports.list

$ sudo apt update
$ sudo apt install libseccomp2 -t buster-backports
```

### Start the container
```sh
$ docker run -dit \
    --env TELEGRAM_BOT_TOKEN=some_token \
    --env TRANSMISSION_HOST=localhost \
    --name=transmission_mgmt_bot transmission_mgmt_bot_image
```
