# coding: utf-8

import os
import threading

from flask import Flask
from influxdb import InfluxDBClient
from kubernetes import client, config

from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from oslo_service import service

from openstack_manager.lib import (util,
                                   helm)

wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)

metrics_map = {}


def launch():
    launcher = service.launch(CONF, ServiceManager())
    launcher.wait()


class ServiceManager(service.Service):
    def __init__(self):
        super(ServiceManager, self).__init__()

    def start(self):
        LOG.info('start')

        if CONF.influxdb.enable:
            self.influxdb_periodic_tasks = InfluxdbPeriodicTasks()
            self.tg.add_dynamic_timer(self._get_influxdb_periodic_tasks,
                                      initial_delay=0,
                                      periodic_interval_max=120)

        if not CONF.rabbitmq_manager.enable_prometheus_exporter:
            self.prometheus_exporter_thread = self._spawn_prometheus_exporter()
        else:
            self.prometheus_exporter_thread = None

        self.periodic_tasks = ServicePeriodicTasks()
        self.tg.add_dynamic_timer(self.get_periodic_tasks,
                                  initial_delay=0,
                                  periodic_interval_max=120)

    def wait(self):
        LOG.info('wait')

    def stop(self):
        LOG.info('stop')

        if self.prometheus_exporter_thread is not None:
            self.prometheus_exporter_thread.join()

        super(ServiceManager, self).stop()

    def _get_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def _get_influxdb_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.influxdb_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def _spawn_prometheus_exporter(self):
        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.openstack_deploy_manager.bind_host,
            'port': CONF.openstack_deploy_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


#
# influxdb reporter
#
class InfluxdbPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(InfluxdbPeriodicTasks, self).__init__(CONF)
        self.influxdb = InfluxDBClient(
            CONF.influxdb.host,
            CONF.influxdb.port,
            CONF.influxdb.user,
            CONF.influxdb.password,
            CONF.influxdb.database,
        )

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=60)
    def report(self, context):
        LOG.info('Report metrics to influxdb')
        json_body = []
        for measurement, metrics in metrics_map.items():
            json_body.append({
                "measurement": measurement.split(':')[0],
                "tags": metrics["tags"],
                "fields": {
                    "value": metrics["value"],
                }
            })

        if len(json_body) > 0:
            self.influxdb.write_points(json_body)


#
# prometheus exporter
#
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
        pmetrics += '{0}{{{1}}} {2}\n'.format(measurement.split(':')[0], labels, metrics['value'])
    return pmetrics


#
# service tasks
#
class ServicePeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(ServicePeriodicTasks, self).__init__(CONF)
        self.resource_map = {}
        self.bin_dir = CONF.openstack_deploy_manager.bin_dir
        self.helm = helm.Helm()

        if os.path.exists('{0}/.kube/config'.format(os.environ['HOME'])):
            config.load_kube_config()
        else:
            config.load_incluster_config()
        self.k8s_corev1api = client.CoreV1Api()

        # execute bootstrap files
        bootstrap_files = []
        for root, dirs, files in os.walk(self.bin_dir):
            for file in files:
                if file.find('bootstrap-') == 0:
                    bootstrap_files.append(os.path.join(root, file))

        bootstrap_files.sort()
        for bootstrap_file in bootstrap_files:
            util.execute(bootstrap_file)

        self.resource_map = self.helm.get_resource_map()

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        LOG.info('Start check')

        # Check helm resources
        tmp_resource_map = self.helm.get_resource_map()
        for resource_name, resource in self.resource_map.items():
            tmp_resource = tmp_resource_map.get[resource_name]
            if tmp_resource['version'] != resource['version']:
                helm_upgrade_script = os.path.join(self.bin_dir,
                                                   'helm-upgrade-{0}'.format(resource_name))
                if os.path.exists(helm_upgrade_script):
                    util.execute(helm_upgrade_script)

        self.resource_name = tmp_resource_map
