# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import server


def main():
    config.init()
    server.launch()
