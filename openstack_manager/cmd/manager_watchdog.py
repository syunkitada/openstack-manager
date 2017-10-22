# coding: utf-8

from openstack_manager.conf import config
from openstack_manager.service import watchdog_wrapper


def k8s_openstack_deploy_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/k8s-openstack-deploy-manager"
    watchdog_wrapper.launch(cmd)


def k8s_openstack_monitor_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/k8s-openstack-monitor-manager"
    watchdog_wrapper.launch(cmd)


def k8s_rabbitmq_manager_main():
    config.init()
    cmd = "/opt/openstack-manager/bin/k8s-rabbitmq-manager"
    watchdog_wrapper.launch(cmd)
