# coding: utf-8

import os
import re
from openstack_manager.lib import util
from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF
LOG = log.getLogger(__name__)

RE_HELM_LIST = re.compile('^([a-zA-Z0-9\-]+)[ \t]+([\d]+)[ \t]+.*[ \t]+([A-Z]+)[ \t]+([a-zA-Z0-9\-]+)-([0-9\.]+)[ \t]+.*')  # noqa


class Helm():
    def __init__(self):
        os.environ['TILLER_NAMESPACE'] = CONF.rabbitmq_manager.tiller_namespace
        self.k8s_namespace = CONF.rabbitmq_manager.k8s_namespace
        self.chart_repo_prefix = CONF.rabbitmq_manager.chart_repo_prefix
        self.values_file_path = CONF.rabbitmq_manager.values_file_path

    def install(self, name, chart):
        util.execute('helm install --namespace {0} --name {1} {2}/{3} -f {4}'.format(
                        self.k8s_namespace, name,  self.chart_repo_prefix, chart,
                        self.values_file_path
                     ))

    def delete(self, name):
        util.execute('helm delete --purge {0}'.format(name))

    def upgrade(self, name, chart, option=''):
        util.execute("helm upgrade {0} {1}/{2} {3}".format(
                        name, self.chart_repo_prefix, chart, option))

    def get_resource_map(self):
        resource_map = {}
        result = util.execute('helm list', )
        for line in result['stdout'].split('\n'):
            m = RE_HELM_LIST.match(line)
            if m is None:
                continue

            resource_name = m.group(1)
            revision = m.group(2)
            status = m.group(3)
            chart = m.group(4)
            version = m.group(5)

            resource_map[resource_name] = {
                'revision': revision,
                'status': status,
                'chart': chart,
                'version': version,
            }

        return resource_map
