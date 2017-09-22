# coding: utf-8

from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from flask import Flask
wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)
periodic_manager = None


@wsgi_app.route("/")
def status():
    return "OK"


@wsgi_app.route("/metrics")
def status():
    return "OK"


def init():
    global periodic_manager
    periodic_manager = PeriodicManager()


class PeriodicManager(periodic_task.PeriodicTasks):
    def __init__(self):
        super(PeriodicManager, self).__init__(CONF)
        self.service_name = 'periodic_manager'

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        LOG.info('start check')
