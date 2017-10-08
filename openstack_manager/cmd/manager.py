# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import openstack_deploy_manager, openstack_monitor_manager, rabbitmq_manager


def openstack_deploy_manager_main():
    config.init()
    openstack_deploy_manager.launch()


def openstack_monitor_manager_main():
    config.init()
    openstack_monitor_manager.launch()


def rabbitmq_manager_main():
    config.init()
    rabbitmq_manager.launch()
