# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import (k8s_openstack_deploy_manager,
                                       k8s_openstack_monitor_manager,
                                       k8s_rabbitmq_manager)


def k8s_openstack_deploy_manager_main():
    config.init()
    k8s_openstack_deploy_manager.launch()


def k8s_openstack_monitor_manager_main():
    config.init()
    k8s_openstack_monitor_manager.launch()


def k8s_rabbitmq_manager_main():
    config.init()
    k8s_rabbitmq_manager.launch()
