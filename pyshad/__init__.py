from .sessions import SQLiteSession, StringSession
from .client import Client
from . import types, utils, filters, exceptions, enums
from time import sleep
from os import sep

__author__ = 'LinuxV3'
__version__ = '0.0.1'

wellcome_text = """Hello dear developer; Hope you enjoy using pyshad
Contact -> Telegram: @LinuxV3
Github -> https://github.com/LinuxV3/"""
print("\033[1;32;40m", end="")
for char in wellcome_text:
    if char == "\n" or char == sep[0]:
        print("\033[0m", end="")
        print()
        print("\033[1;32;40m", end="")
        continue
    print(char, end="", flush=True)
    sleep(0.04)
print("\033[0m")
