#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import telebot
import os
import transmissionrpc
import logging as log
import signal
import sys
import bencodepy
import hashlib
import base64
import re
from urllib.request import Request, urlopen
from get_ip import get_ip_of_running_transmission, trigger_terraform


AUTHORIZED_USERS = [int(x) for x in os.getenv('AUTHORIZED_USERS', '294967926,191151492').split(",")]

class Transmission:
    def __init__(self):
        try:
            self.tc = transmissionrpc.Client(
                address=os.getenv('TRANSMISSION_HOST', get_ip_of_running_transmission()),
                port=os.getenv('TRANSMISSION_PORT', 9091),
                user=os.getenv('TRANSMISSION_USER', 'transmission'),
                password=os.getenv('TRANSMISSION_PASSWORD', 'transmission'),
            )
        except transmissionrpc.error.TransmissionError:
            print("ERROR: Failed to connect to Transmission. Check rpc configuration.")
            sys.exit()

    def get_torrents(self):
        torrents = [
            [t.id, t.name, t.status, round(t.progress, 2)]
            for t in self.tc.get_torrents()
        ]
        return torrents

    def get_files(self, torrent_ids):
        files_list = []
        files_dict = self.tc.get_files(torrent_ids)
        for torrent_id, files in files_dict.items():
            for file_id, props in files.items():
                files_list.append(
                    "[{0}] {1} {2} MB".format(
                        file_id, props["name"], round(int(props["size"]) / 1048576)
                    )
                )
        return files_list

    def get_torrents_with_files(self):
        torrents = self.get_torrents()
        torrents_dict = {}
        for torrent in torrents:
            torrents_dict[" ".join(str(e) for e in torrent)] = self.get_files(
                torrent[0]
            )
        return torrents_dict

    def add_torrent(self, torrent_link):
        add_result = self.tc.add_torrent(
            torrent_link,
            download_dir=os.path.join(
                os.getenv('TRANSMISSION_DOWNLOAD_DIR', '/tmp/downloads'),
                time.strftime("%d%m%Y%H%M%S"),
            ),
        )
        return add_result.id

    def start_torrents(self, torrent_ids):
        existing_torrent_ids = list(
            set(torrent_ids).intersection([f"{t.id}" for t in self.tc.get_torrents()])
        )
        if existing_torrent_ids:
            self.tc.start_torrent(existing_torrent_ids)
        return 0
    
    def set_wanted(self, torrent_id, file_ids):
        files_dict = self.tc.get_files([torrent_id])
        for torrent_id, files in files_dict.items():
            for file_id, props in files.items():
                if file_id not in file_ids:
                    files_dict[torrent_id][file_id]['selected'] = False
        result = self.tc.set_files(files_dict)
        return result

    def delete_torrents(self, torrent_ids):
        existing_torrent_ids = list(
            set(torrent_ids).intersection([f"{t.id}" for t in self.tc.get_torrents()])
        )
        if existing_torrent_ids:
            self.tc.remove_torrent(existing_torrent_ids)
        return 0

bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'), threaded=False)


def log_and_send_message_decorator(fn):
    def wrapper(message):
        bot.send_message(message.chat.id, f"Executing your command, please wait...")
        log.info("[FROM {}] [{}]".format(message.chat.id, message.text))
        if message.chat.id in AUTHORIZED_USERS:
            reply = fn(message)
        else:
            reply = "Sorry, this is a private bot"
        log.info("[TO {}] [{}]".format(message.chat.id, reply))
        bot.send_message(message.chat.id, reply)

    return wrapper


def find_magnet_links_by_url(page_url):
    req = Request(page_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as response:
        charset = response.headers.get_content_charset()
        if charset is None:
            charset = "utf-8"
        content = response.read().decode(charset)
        links = re.findall("href=[\"'](.*?)[\"']", content)
        magnet_links = [link for link in links if link.startswith("magnet:?")]
        return magnet_links


@bot.message_handler(commands=["start", "help"])
@log_and_send_message_decorator
def greet_new_user(message):
    welcome_msg = (
        "\nWelcome to Transmission management bot!\nCommands available:\n"
        "/add - Add torrent to transfers list by URL or magnet link.\n"
        "/list - Print information for current torrents with provided ids\n"
        "/list+files - Print information for current torrents with files listing\n"
        "/delete - Delete torrent from transfers list by IDs\n"
        "/stop - Stop torrent by IDs\n"
        "/go - Start torrent by IDs\n"
        "/help - Print help message"
    )
    if message.chat.first_name is not None:
        if message.chat.last_name is not None:
            reply = "Hello, {} {} {}".format(
                message.chat.first_name, message.chat.last_name, welcome_msg
            )
        else:
            reply = "Hello, {} {}".format(message.chat.first_name, welcome_msg)
    else:
        reply = "Hello, {} {}".format(message.chat.title, welcome_msg)
    return reply


@bot.message_handler(commands=["list"])
@log_and_send_message_decorator
def list_all_torrents(message):
    transmission = Transmission()
    torrents = transmission.get_torrents()
    if torrents:
        reply = "Active torrents:\n"
        for torrent in torrents:
            reply += "#{0}\n".format(" ".join(str(e) for e in torrent))
    else:
        reply = "There are no active torrents"
    return reply


@bot.message_handler(commands=["list_w_files"])
@log_and_send_message_decorator
def list_all_torrents_with_files(message):
    transmission = Transmission()
    torrents = transmission.get_torrents_with_files()
    if torrents:
        reply = "Active torrents:\n"
        for torrent_info, files_info in torrents.items():
            reply += "#{0}\n".format(torrent_info)
            for file_info in files_info:
                reply += "{0}\n".format(file_info)
    else:
        reply = "There are no active torrents"
    return reply


@bot.message_handler(commands=["wanted"])
@log_and_send_message_decorator
def list_all_torrents_with_files(message):
    split_message = message.text.replace("/wanted ", "", 1).split()
    transmission = Transmission()
    transmission.set_wanted(split_message[0], [int(x) for x in split_message[1:]])
    return f"Torrent {split_message[0]} download only {split_message[1:]}"


@bot.message_handler(func=lambda m: m.text is not None and m.text.startswith(("/add", "magnet:?", "https://")))
@log_and_send_message_decorator
def add_new_torrent(message):
    magnet_link = ""
    if message.text.startswith(("/add")):
        magnet_link = message.text.replace("/add ", "", 1)
    elif message.text.startswith(("magnet:?")):
        magnet_link = message.text
    elif message.text.startswith(("https://")):
        try:
            magnet_links = find_magnet_links_by_url(message.text)
        except:
            magnet_links = []
        if len(magnet_links) == 0:
            return "Can't find a magnet link for your URL, please provide it directly"
        else:
            magnet_link = magnet_links[0]
    if "magnet:?" in magnet_link:
        transmission = Transmission()
        add_result = transmission.add_torrent(magnet_link)
        reply = "Torrent was successfully added with ID #{0}".format(add_result)
    else:
        reply = "Please check your magnet link and try again"
    return reply


@bot.message_handler(content_types=["document"])
@log_and_send_message_decorator
def add_new_torrent_by_file(message):
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    torrent_file_name = "{}.torrent".format(time.strftime("%d%m%Y%H%M%S"))
    with open(torrent_file_name, "wb") as new_file:
        new_file.write(downloaded_file)
        metadata = bencodepy.decode_from_file(torrent_file_name)
        subj = metadata[b"info"]
        hashcontents = bencodepy.encode(subj)
        digest = hashlib.sha1(hashcontents).digest()
        b32hash = base64.b32encode(digest).decode()
        transmission = Transmission()
        add_result = transmission.add_torrent("magnet:?xt=urn:btih:" + b32hash)
        os.remove(torrent_file_name)
        return "Torrent was successfully added with ID #{0}".format(add_result)


@bot.message_handler(commands=["go"])
@log_and_send_message_decorator
def add_new_torrent(message):
    torrent_ids = message.text.replace("/go ", "", 1).split()
    transmission = Transmission()
    transmission.start_torrents(torrent_ids)
    return "Torrents with IDs {0} were started.\n".format(
        " ".join(str(e) for e in torrent_ids)
    )


@bot.message_handler(commands=["delete"])
@log_and_send_message_decorator
def delete_torrents(message):
    transmission = Transmission()
    torrent_ids = message.text.replace("/delete ", "", 1).split()
    transmission.delete_torrents(torrent_ids)
    return "Torrents with IDs {0} were deleted.\n".format(
        " ".join(str(e) for e in torrent_ids)
    )


@bot.message_handler(commands=["destroy"])
@log_and_send_message_decorator
def send_destroy_request(message):
    trigger_terraform("true", "Destroy from bot with command")
    return "Destroy request was sent"


def signal_handler(signal_number, frame):
    print("Received signal " + str(signal_number) + ". Trying to end tasks and exit...")
    bot.stop_polling()
    sys.exit(0)


def main():
    log.basicConfig(level=log.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Bot was started.")
    signal.signal(signal.SIGINT, signal_handler)
    log.info("Starting bot polling...")
    bot.polling()


if __name__ == "__main__":
    main()
