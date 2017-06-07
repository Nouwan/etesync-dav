#!/usr/bin/env python

import argparse
from configparser import RawConfigParser as ConfigParser
import getpass
import os
import random
import string

import etesync as api
from radicale_storage_etesync import creds, CONFIG_SECTION

from etesync_dav.config import CONFIG_DIR, HTPASSWD_FILE, CREDS_FILE, RADICALE_CONFIG_FILE


class Htpasswd:
    def __init__(self, filename):
        self.filename = filename
        self.load()

    def load(self):
        with open(self.filename, "r") as f:
            self.content = dict(map(lambda x: x.strip(), line.split(':', 1)) for line in f)

    def save(self):
        with open(self.filename, "w") as f:
            for name, password in self.content.items():
                print("{}:{}".format(name, password), file=f)

    def get(self, username):
        return self.content.get(username, None)

    def set(self, username, password):
        self.content[username] = password

    def delete(self, username):
        self.content.pop(username, None)

    def list(self):
        for item in self.content.keys():
            yield item


def validate_username(htpasswd, username):
    if username is None:
        raise RuntimeError("Username is required")
    if ':' in username:
        raise RuntimeError("Username can't include a colon.")
    return htpasswd.get(username) is not None


def print_credentials(htpasswd, username):
    print("User: {}\nPassword: {}".format(args.username, htpasswd.get(args.username)))


parser = argparse.ArgumentParser()
parser.add_argument("command",
                    choices=('add', 'del', 'get', 'list'),
                    help="Either add to add a user, del to remove a user, get to show login creds, " +
                         "or list to list all users.")
parser.add_argument("username",
                    nargs='?',
                    help="The username used with EteSync")
parser.add_argument("--login-password",
                    help="The password to login to the EteSync server.")
parser.add_argument("--encryption-password",
                    help="The encryption password")
args = parser.parse_args()

if not os.path.exists(CONFIG_DIR):
    os.mkdir(CONFIG_DIR)

htpasswd = Htpasswd(HTPASSWD_FILE)
creds = creds.Credentials(CREDS_FILE)
radicale_config = ConfigParser()
radicale_config.read(RADICALE_CONFIG_FILE)

remote_url = radicale_config.get(CONFIG_SECTION, "remote_url")
db_path = radicale_config.get(CONFIG_SECTION, "database_filename")
creds_path = radicale_config.get(CONFIG_SECTION, "credentials_filename")

if args.command == 'add':
    exists = validate_username(htpasswd, args.username)
    if exists:
        raise RuntimeError("User already exists. Delete first if you'd like to override settings.")

    login_password = (getattr(args, 'login_password') or
                      getpass.getpass(prompt="Please enter the EteSync login password: "))
    encryption_password = (getattr(args, 'encryption_password') or
                           getpass.getpass(prompt="Please enter your encryption password: "))

    print("Fetching auth token")
    auth_token = api.Authenticator(remote_url).get_auth_token(args.username, login_password)

    print("Deriving password")
    etesync = api.EteSync(args.username, auth_token, remote=remote_url)
    cipher_key = etesync.derive_key(encryption_password)

    print("Saving config")
    generated_password = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
    htpasswd.set(args.username, generated_password)
    creds.set(args.username, auth_token, cipher_key)
    htpasswd.save()
    creds.save()

    print_credentials(htpasswd, args.username)

elif args.command == 'del':
    exists = validate_username(htpasswd, args.username)
    if not exists:
        raise RuntimeError("User not found")

    print("Deleting user")
    htpasswd.delete(args.username)
    creds.delete(args.username)
    htpasswd.save()
    creds.save()

elif args.command == 'get':
    exists = validate_username(htpasswd, args.username)
    if not exists:
        raise RuntimeError("User not found")

    print_credentials(htpasswd, args.username)

elif args.command == 'list':
    for user in htpasswd.list():
        print(user)