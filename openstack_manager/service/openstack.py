# coding: utf-8

import threading
import time
from datetime import datetime

from flask import Flask
from influxdb import InfluxDBClient

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
metrics_map = {}


def launch():
    launcher = service.launch(CONF, OpenstackService())
    launcher.wait()


@wsgi_app.route("/")
def status():
    return "OK"


@wsgi_app.route("/metrics")
def metrics():
    pmetrics = ''
    for measurement, metrics in metrics_map.items():
        labels = ''
        for k, v in metrics['tags'].items():
            labels += '{0}="{1}",'.format(k, v)
        labels = labels[:-1]
        pmetrics += '{0}{{{1}}} {2}\n'.format(measurement, labels, metrics['value'])
    return pmetrics


class OpenstackService(service.Service):
    def __init__(self, name='openstack_manager'):
        super(OpenstackService, self).__init__()

    def start(self):
        LOG.info('start')
        self.openstack_periodic_tasks = OpenstackPeriodicTasks()
        self.influxdb_periodic_tasks = InfluxdbPeriodicTasks()
        self.wsgi_thread = self.spawn_app()
        self.tg.add_dynamic_timer(self.get_openstack_periodic_tasks,
                                  initial_delay=0,
                                  periodic_interval_max=120)

        if CONF.openstack_manager.enable_influxdb:
            self.tg.add_dynamic_timer(self.get_influxdb_periodic_tasks,
                                      initial_delay=0,
                                      periodic_interval_max=120)

    def wait(self):
        LOG.info('wait')

    def stop(self):
        LOG.info('stop')

        if self.wsgi_thread:
            self.wsgi_thread.join()

        super(OpenstackService, self).stop()

    def get_openstack_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.openstack_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def get_influxdb_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.influxdb_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)

        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.openstack_manager.bind_host,
            'port': CONF.openstack_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


class OpenstackPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(OpenstackPeriodicTasks, self).__init__(CONF)
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
        LOG.info('Start check openstack')

        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        start_time = time.time()
        self.keystone.projects.list()
        elapsed_time = time.time() - start_time
        metrics_map['openstack_keystone_project_list_latency'] = {
            'tags': {"svc": "keystone"},
            'value': elapsed_time,
            'time': timestamp,
        }

        start_time = time.time()
        self.neutron.list_networks()
        elapsed_time = time.time() - start_time
        metrics_map['openstack_neutron_network_list_latency'] = {
            'tags': {"svc": "neutron"},
            'value': elapsed_time,
            'time': timestamp,
        }

        start_time = time.time()
        self.nova.flavors.list()
        elapsed_time = time.time() - start_time
        metrics_map['openstack_nova_flavor_list_latency'] = {
            'tags': {"svc": "nova"},
            'value': elapsed_time,
            'time': timestamp,
        }

        start_time = time.time()
        self.glance.images.list()
        elapsed_time = time.time() - start_time
        metrics_map['openstack_glance_image_list_latency'] = {
            'tags': {"svc": "glance"},
            'value': elapsed_time,
            'time': timestamp,
        }

        LOG.info(metrics_map)


class InfluxdbPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(InfluxdbPeriodicTasks, self).__init__(CONF)
        self.influxdb = InfluxDBClient('10.32.237.184', 8086, 'root', 'rootpass', 'openstack')

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=60)
    def report(self, context):
        LOG.info('report influxdb')
        json_body = []
        for measurement, metrics in metrics_map.items():
            json_body.append({
                "measurement": measurement,
                "tags": metrics["tags"],
                "fields": {
                    "value": metrics["value"],
                }
            })

        self.influxdb.write_points(json_body)
