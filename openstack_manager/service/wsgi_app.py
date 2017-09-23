# coding: utf-8

import time
from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from flask import Flask
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)
periodic_manager = None
pmetrics = ""


@wsgi_app.route("/")
def status():
    return "OK"


@wsgi_app.route("/metrics")
def metrics():
    return pmetrics


def init():
    global periodic_manager
    periodic_manager = PeriodicManager()


class PeriodicManager(periodic_task.PeriodicTasks):
    def __init__(self):
        super(PeriodicManager, self).__init__(CONF)
        self.service_name = 'periodic_manager'
        auth = v3.Password(auth_url='https://keystone-public.k8s.example.com/v3', username="admin",
                           password="adminpass", project_name="admin",
                           user_domain_id="default", project_domain_id="default")
        sess = session.Session(auth=auth, verify=False)
        self.keystone = keystone_client.Client(session=sess)
        self.neutron = neutron_client.Client(session=sess)

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        global pmetrics
        LOG.info('start check')
        tmp_pmetrics = ""

        start_time = time.time()
        project_list = self.keystone.projects.list()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_keystone_project_list_latency{{svc="keystone"}} {0}\n'.format(elapsed_time)

        start_time = time.time()
        network_list = self.neutron.list_networks()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_neutron_network_list_latency{{svc="neutron"}} {0}\n'.format(elapsed_time)
        pmetrics = tmp_pmetrics
        LOG.info(pmetrics)
