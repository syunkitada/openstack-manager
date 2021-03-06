# coding: utf-8

from oslo_config import cfg
from oslo_log import log
from openstack_manager.conf import constant, opts

LOG = log.getLogger(__name__)

CONF = cfg.CONF
CONF.register_opts(opts.k8s_opts, 'k8s')
CONF.register_opts(opts.influxdb_opts, 'influxdb')
CONF.register_opts(opts.openstack_auth_opts, 'openstack_auth')
CONF.register_opts(opts.openstack_deploy_manager_opts, 'openstack_deploy_manager')
CONF.register_opts(opts.openstack_monitor_manager_opts, 'openstack_monitor_manager')
CONF.register_opts(opts.rabbitmq_manager_opts, 'rabbitmq_manager')


def init():
    log.register_options(CONF)
    CONF([], default_config_files=[constant.INIFILE])
    log.setup(CONF, constant.LOG_DOMEIN)
    LOG.info('init conf')
