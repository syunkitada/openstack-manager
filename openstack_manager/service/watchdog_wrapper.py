# coding: utf-8

import os
import time
import subprocess
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from oslo_log import log
from oslo_config import cfg

BASEDIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
LOG = log.getLogger(__name__)
CONF = cfg.CONF


class WatchdogService():
    def __init__(self, cmd):
        self.cmd = cmd

    def start(self):
        event_handler = EventHandler(self.cmd)
        observer = Observer()
        observer.schedule(event_handler, BASEDIR, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()


class EventHandler(FileSystemEventHandler):
    def __init__(self, cmd):
        super(EventHandler, self).__init__()
        self.cmd = cmd
        self.proc = subprocess.Popen(cmd.split(' '))

    def reload_script(self, src_path):
        if src_path[-3:] == '.py':
            if self.proc is not None:
                LOG.info('Stop: {0}'.format(self.cmd))
                self.proc.kill()

            LOG.info('Start: {0}'.format(self.cmd))
            self.proc = subprocess.Popen(self.cmd.split(' '))

    def on_created(self, event):
        if event.is_directory:
            return

    def on_modified(self, event):
        if event.is_directory:
            return
        self.reload_script(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.reload_script(event.src_path)


def launch(cmd):
    watchdog_service = WatchdogService(cmd)
    watchdog_service.start()
