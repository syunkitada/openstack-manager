# coding: utf-8

import os
import threading
import traceback
import time
from datetime import datetime

from flask import Flask
from influxdb import InfluxDBClient
from kombu import Connection, Exchange, Queue
from kubernetes import client, config

from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from oslo_service import service

from openstack_manager.lib import util, helm

wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)

metrics_map = {}


def launch():
    launcher = service.launch(CONF, OpenstackDeployManager())
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


class OpenstackDeployManager(service.Service):
    def __init__(self):
        super(OpenstackDeployManager, self).__init__()

    def start(self):
        LOG.info('start')
        self.periodic_tasks = OpenstackDeployManagerPeriodicTasks()
        self.influxdb_periodic_tasks = InfluxdbPeriodicTasks()
        self.wsgi_thread = self.spawn_app()
        self.tg.add_dynamic_timer(self.get_periodic_tasks,
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

        super(OpenstackDeployManager, self).stop()

    def get_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def get_influxdb_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.influxdb_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)

        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.openstack_deploy_manager.bind_host,
            'port': CONF.openstack_deploy_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


class OpenstackDeployManagerPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(OpenstackDeployManagerPeriodicTasks, self).__init__(CONF)
        self.file_map = {}
        self.resource_map = {}
        self.bin_dir = CONF.openstack_deploy_manager.bin_dir
        self.values_file = CONF.openstack_manager.values_file

        if os.path.exists('{0}/.kube/config'.format(os.environ['HOME'])):
            config.load_kube_config()
        else:
            config.load_incluster_config()
        self.k8s_corev1api = client.CoreV1Api()

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        LOG.info('Start check')

        bootstrap_files = []
        for root, dirs, files in os.walk(self.bin_dir):
            for file in files:
                if file.find('bootstrap-') == 0:
                    bootstrap_file = os.path.join(root, file)
                    bootstrap_files.append(bootstrap_file)

        bootstrap_files.sort()
        for bootstrap_file in bootstrap_files:
            bootstrap = self.file_map.get(bootstrap_file, {
                'current_hash': '',
            })
            tmp_hash = util.sha256(bootstrap_file)
            if tmp_hash != bootstrap['current_hash']:
                LOG.info('{0} is changed'.format(bootstrap_file))
                cmd = bootstrap_file
                result = util.execute(cmd)

                bootstrap['current_hash'] = tmp_hash
                self.file_map[bootstrap_file] = bootstrap

        # Check helm resources
        result = util.execute('helm list')

        # When values file is updated, update helm resources.
        tmp_hash = util.sha256(self.values_file)
        tmp_file = self.file_map.get(self.values_file, {
            'current_hash': '',
        })

        # When remote charts are updated, update helm resources.
        return
        for line in result['stdout'].split('\n'):
            m = RE_HELM_LIST.match(line)
            if m is None:
                continue

            resource_name = m.group(1)
            chart = m.group(2)
            version = m.group(3)
            resource = resource_map.get(resource_name)
            if resource is None:
                resource_map[resource_name] = {
                    'chart': chart,
                    'version': version,
                }
            else:
                if version != resource['version']:
                    util.execute('helm update {0} {1} -f {2}'.format(
                        resource_name, chart, VALUES_FILE
                    ))
                    resource_map[resource_name]['version'] = version

        result = util.execute('helm repo update')


class InfluxdbPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(InfluxdbPeriodicTasks, self).__init__(CONF)
        self.influxdb = InfluxDBClient(
            CONF.openstack_manager.influxdb_host,
            CONF.openstack_manager.influxdb_port,
            CONF.openstack_manager.influxdb_user,
            CONF.openstack_manager.influxdb_password,
            CONF.openstack_manager.influxdb_database,
        )

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

        if len(json_body) > 0:
            self.influxdb.write_points(json_body)
