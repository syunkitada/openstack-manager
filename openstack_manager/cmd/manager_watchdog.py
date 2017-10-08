# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import watchdog_wrapper


def openstack_deploy_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/openstack-deploy-manager"
    watchdog_wrapper.launch(cmd)


def openstack_monitor_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/openstack-monitor-manager"
    watchdog_wrapper.launch(cmd)


def rabbitmq_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/rabbitmq-manager"
    watchdog_wrapper.launch(cmd)
