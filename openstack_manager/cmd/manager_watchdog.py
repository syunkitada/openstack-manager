# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import watchdog_wrapper


def openstack_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/openstack-manager"
    watchdog_wrapper.launch(cmd)


def rabbitmq_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/rabbitmq-manager"
    watchdog_wrapper.launch(cmd)
