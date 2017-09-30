# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import openstack, rabbitmq


def openstack_main():
    config.init()
    openstack.launch()


def rabbitmq_main():
    config.init()
    rabbitmq.launch()
