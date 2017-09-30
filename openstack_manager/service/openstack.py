# coding: utf-8

import threading
import time

from flask import Flask

from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from oslo_service import service

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from novaclient import client as nova_client
import glanceclient as glance_client

wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)
pmetrics = ""


def launch():
    launcher = service.launch(CONF, OpenStackService())
    launcher.wait()


@wsgi_app.route("/")
def status():
    return "OK"


@wsgi_app.route("/metrics")
def metrics():
    return pmetrics


class OpenStackService(service.Service):
    def __init__(self, name='openstack_manager'):
        super(OpenStackService, self).__init__()

    def start(self):
        LOG.info('start')
        self.periodic_service = PeriodicService()
        self.wsgi_thread = self.spawn_app()
        self.tg.add_dynamic_timer(self.periodic_tasks,
                                  initial_delay=0,
                                  periodic_interval_max=120)

    def wait(self):
        LOG.info('wait')

    def stop(self):
        LOG.info('stop')

        if self.wsgi_thread:
            self.wsgi_thread.join()

        super(OpenStackService, self).stop()

    def periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.periodic_service.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)

        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.openstack_manager.bind_host,
            'port': CONF.openstack_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


class PeriodicService(periodic_task.PeriodicTasks):
    def __init__(self):
        super(PeriodicService, self).__init__(CONF)
        self.service_name = 'periodic_service'
        auth = v3.Password(auth_url='https://keystone-public.k8s.example.com/v3', username="admin",
                           password="adminpass", project_name="admin",
                           user_domain_id="default", project_domain_id="default")
        sess = session.Session(auth=auth, verify=False)
        self.keystone = keystone_client.Client(session=sess)
        self.neutron = neutron_client.Client(session=sess)
        self.nova = nova_client.Client('2.1', session=sess)
        self.glance = glance_client.Client('2', session=sess)

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        global pmetrics
        LOG.info('start check')
        tmp_pmetrics = ""

        start_time = time.time()
        self.keystone.projects.list()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_keystone_project_list_latency{{svc="keystone"}} {0}\n'.format(elapsed_time)

        start_time = time.time()
        self.neutron.list_networks()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_neutron_network_list_latency{{svc="neutron"}} {0}\n'.format(elapsed_time)

        start_time = time.time()
        self.nova.flavors.list()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_nova_flavor_list_latency{{svc="nova"}} {0}\n'.format(elapsed_time)

        start_time = time.time()
        self.glance.images.list()
        elapsed_time = time.time() - start_time
        tmp_pmetrics += 'openstack_glance_image_list_latency{{svc="glance"}} {0}\n'.format(elapsed_time)

        pmetrics = tmp_pmetrics
        LOG.info(pmetrics)
