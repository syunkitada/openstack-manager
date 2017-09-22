# coding: utf-8

import time
import os
import subprocess

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

BASEDIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
proc = None
cmd = "/opt/openstack-manager/bin/openstack-api"


def main():
    global proc
    proc = subprocess.Popen(cmd.split(' '))

    while True:
        event_handler = ChangeHandler()
        observer = Observer()
        observer.schedule(event_handler, BASEDIR, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()


def reload_script(src_path):
    global proc
    if src_path[-3:] == '.py':
        if proc is not None:
            proc.kill()

        proc = subprocess.Popen(cmd.split(' '))


class ChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

    def on_modified(self, event):
        if event.is_directory:
            return
        reload_script(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        reload_script(event.src_path)
