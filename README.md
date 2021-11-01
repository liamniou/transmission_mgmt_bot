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

### Start the container
```sh
$ docker run -dit \
    --env TELEGRAM_BOT_TOKEN=some_token \
    --env TRANSMISSION_HOST=localhost \
    --name=transmission_mgmt_bot -v transmission_mgmt_bot_app:/app transmission_mgmt_bot_image
```