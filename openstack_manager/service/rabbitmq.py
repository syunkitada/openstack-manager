# coding: utf-8

import threading
import traceback
import time
import re
import json
from datetime import datetime

from flask import Flask
from influxdb import InfluxDBClient
from kombu import Connection, Exchange, Queue

from oslo_service import periodic_task
from oslo_config import cfg
from oslo_log import log
from oslo_service import service

from openstack_manager.lib import util

wsgi_app = Flask(__name__)

CONF = cfg.CONF
LOG = log.getLogger(__name__)

metrics_map = {}

RE_HELM_LIST = re.compile('^([a-zA-Z0-9\-]+)[ \t]+([\d]+)[ \t]+.*[ \t]+([A-Z]+)[ \t]+([a-zA-Z0-9\-]+)-([0-9\.]+)[ \t]+.*')
STATUS_NOT_INSTALLED = -1
STATUS_INSTALLED = 0
STATUS_ACTIVE = 1
STATUS_ACTIVE_ALL_GREEN = 2


def launch():
    launcher = service.launch(CONF, RabbitmqService())
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


class RabbitmqService(service.Service):
    def __init__(self):
        super(RabbitmqService, self).__init__()

    def start(self):
        LOG.info('start')
        self.rabbitmq_periodic_tasks = RabbitmqPeriodicTasks()
        self.influxdb_periodic_tasks = InfluxdbPeriodicTasks()
        self.wsgi_thread = self.spawn_app()
        self.tg.add_dynamic_timer(self.get_rabbitmq_periodic_tasks,
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

        super(RabbitmqService, self).stop()

    def get_rabbitmq_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.rabbitmq_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def get_influxdb_periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return self.influxdb_periodic_tasks.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)

        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.rabbitmq_manager.bind_host,
            'port': CONF.rabbitmq_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


class RabbitmqPeriodicTasks(periodic_task.PeriodicTasks):
    def __init__(self):
        super(RabbitmqPeriodicTasks, self).__init__(CONF)

        self.user = CONF.rabbitmq_manager.user
        self.password = CONF.rabbitmq_manager.password
        self.cluster_pool = set()
        self.cluster_map = {}
        self.svc_map = {}
        self.helm_resource_map = {}

        self.update_helm_resource_map()

        result = util.execute("kubectl get node -l rabbitmq-node=enable")
        rabbit_hosts = []
        for line in result['stdout'].split('\n'):
            if line.find(' Ready ') > 0:
                rabbit_hosts.append(line.split(' ', 1)[0])

        if len(rabbit_hosts) < 1:
            raise Exception('rabbit_hosts are not found')

        # initialize cluster_map
        pool_count = len(CONF.rabbitmq_manager.services) + CONF.rabbitmq_manager.cluster_backups
        for id in range(pool_count):
            name = 'rabbitmq-cluster-{0}'.format(id)
            self.cluster_pool.add(name)
            self.cluster_map[name] = {
                'provisioning_status': STATUS_NOT_INSTALLED,
                'assigned_svc': None,
                'connection': 'amqp://{0}:{1}@{2}:5672/test'.format(self.user, self.password, name),
                'warning': {
                    'exists_unhealty_pods': 0,
                    'exists_standalone_nodes': 0,
                    'failed_get_cluster_status': 0,
                }
            }

        # initialize svc_map
        for svc_vhost in CONF.rabbitmq_manager.services:
            name = 'rabbitmq-svc-{0}'.format(svc_vhost)
            self.svc_map[name] = {
                'provisioning_status': STATUS_NOT_INSTALLED,
                'vhost': '{0}'.format(svc_vhost),
                'selector': None,
            }

        # helm install svc_map, and set transport_url
        for name, svc in self.svc_map.items():
            if name not in self.helm_resource_map:
                util.execute('helm install --name {0} --tiller-namespace {1} --namespace {2} {3}/rabbitmq-svc'.format(
                    name, CONF.rabbitmq_manager.tiller_namespace,
                    CONF.rabbitmq_manager.k8s_namespace, CONF.rabbitmq_manager.chart_repo_prefix
                ))
                svc['provisioning_status'] = STATUS_INSTALLED
            else:
                svc['provisioning_status'] = STATUS_ACTIVE
                result = util.execute("kubectl get svc -n {0} {1} -o jsonpath='{{.spec.selector.app}}'".format(
                    CONF.rabbitmq_manager.k8s_namespace, name))
                svc['selector'] = result['stdout']

            transport_url = 'rabbit:\\\\/\\\\/'
            result = util.execute("kubectl get svc -n {0} {1} -o jsonpath={{.spec.ports[0].nodePort}}".format(
                CONF.rabbitmq_manager.k8s_namespace, name
            ))
            rabbit_port = result['stdout']
            for host in rabbit_hosts:
                if host == '':
                    continue
                transport_url += "{0}:{1}@{2}:{3}\,".format(
                    self.user, self.password, host, rabbit_port
                )
            transport_url = transport_url[0:-2] + '\\\\/' + svc['vhost']
            svc['transport_url'] = transport_url

    def update_helm_resource_map(self):
        self.helm_resource_map = {}
        result = util.execute('helm list --tiller-namespace {0}'.format(CONF.rabbitmq_manager.tiller_namespace))
        for line in result['stdout'].split('\n'):
            m = RE_HELM_LIST.match(line)
            if m is None:
                continue

            resource_name = m.group(1)
            revision = m.group(2)
            status = m.group(3)
            chart = m.group(4)
            version = m.group(5)

            self.helm_resource_map[resource_name] = {
                'revision': revision,
                'status': status,
                'chart': chart,
                'version': version,
            }

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        LOG.info('Start check')
        self.update_helm_resource_map()

        for name, cluster in self.cluster_map.items():
            if name not in self.helm_resource_map:
                util.execute('helm install --name {0} --tiller-namespace {1} --namespace {2} {3}/rabbitmq-cluster -f {4}'.format(
                    name, CONF.rabbitmq_manager.tiller_namespace, CONF.rabbitmq_manager.k8s_namespace,
                    CONF.rabbitmq_manager.chart_repo_prefix, CONF.rabbitmq_manager.values_file_path
                ))
                cluster['provisioning_status'] = STATUS_INSTALLED
            else:
                cluster['provisioning_status'] = STATUS_ACTIVE

            result = util.execute('kubectl get pod -n {0} -l app={1} -o json'.format(CONF.rabbitmq_manager.k8s_namespace, name))
            print json.loads(result['stdout'])

            return
            pods = 0
            running_pods = 0
            running_nodes = 0
            unhealty_pods = 0
            failed_get_cluster_status = 0
            is_partition = False
            is_healty = True
            for line in result['stdout'].split('\n'):
                if line.find('Error') > 1 or line.find('Crash') > 1:
                    LOG.error('Pod is error, these node will be self.destroyed')
                    self.destroy(name)

                pods += 1
                if line.find('Running') == -1:
                    continue
                if line.find(' 1/1 ') == -1:
                    unhealty_pods += 1
                    continue

                running_pods += 1

                pod = line.split(' ', 1)[0]
                LOG.error("DEBUG11111")
                cluster_status = self.get_cluster_status(pod)
                LOG.error("DEBUG222222")
                if cluster_status is None:
                    failed_get_cluster_status += 1

                if cluster_status['is_partition']:
                    is_partition = True
                    break

                running_nodes += cluster_status['running_nodes']

            if is_partition:
                self.destroy(name)
                continue

            LOG.error("DEBUG 3333")
            if running_pods >= 2 and not self.test_queue(cluster):
                self.destroy(name)
                continue
            LOG.error("DEBUG 4444")

            if unhealty_pods != 0:
                is_healty = False
                LOG.warning('Found unhealty_pods')
                cluster['warning']['exists_unhealty_pods'] += unhealty_pods
                destroy_threshold = CONF.rabbitmq_manager.wait_unhealty_pods_time / CONF.rabbitmq_manager.check_interval
                if cluster['provisioning_status'] < 1:
                    destroy_threshold = destroy_threshold * pods

                if cluster['warning']['exists_unhealty_pods'] >= destroy_threshold:
                    self.destroy(name)
            else:
                cluster['warning']['exists_unhealty_pods'] = 0

                standalone_pods = (running_pods * running_pods) - running_nodes
                if standalone_pods != 0:
                    is_healty = False
                    LOG.warning('Found standalone_pods')
                    cluster['warning']['exists_standalone_nodes'] += 1
                    if cluster['warning']['exists_standalone_nodes'] >= 2:
                        self.destroy(name)
                else:
                    cluster['warning']['exists_standalone_nodes'] = 0

                if failed_get_cluster_status != 0:
                    is_healty = False
                    LOG.warning('Failed get cluster_status')
                    cluster['warning']['failed_get_cluster_status'] += 1
                    if cluster['warning']['failed_get_cluster_status'] >= 2:
                        self.destroy(name)
                else:
                    cluster['warning']['failed_get_cluster_status'] = 0

                if is_healty:
                    cluster['provisioning_status'] = 1

        LOG.error("DEBUG 5555")
        self.assign_services_to_cluster()
        LOG.info("Check Summary")
        for cluster_name, cluster in self.cluster_map.items():
            LOG.info("{0}: {1}".format(cluster_name, cluster))

    def get_cluster_status(self, pod_name):
        cluster_status = util.execute('kubectl exec -n {0} {1} rabbitmqctl cluster_status'.format(
            CONF.rabbitmq_manager.k8s_namespace, pod_name),
                                      enable_exception=False)
        if cluster_status['return_code'] != 0:
            return None

        splited_msg = cluster_status['stdout'].split('{nodes', 1)
        splited_msg = splited_msg[1].split('{running_nodes,', 1)
        tmp_splited_msg = splited_msg[1].split('{cluster_name,', 1)
        if len(tmp_splited_msg) == 2:
            running_nodes = tmp_splited_msg[0]
            splited_msg = tmp_splited_msg[1].split('{partitions,', 1)
        else:
            splited_msg = splited_msg[1].split('{partitions,', 1)
            running_nodes = splited_msg[0]

        tmp_splited_msg = splited_msg[1].split('{alarms,', 1)
        if len(tmp_splited_msg) == 2:
            partitions = tmp_splited_msg[0]
        else:
            splited_msg = splited_msg[1].split('}]', 1)
            partitions = splited_msg[0]

        running_nodes_count = running_nodes.count('@')
        partitions_count = partitions.count('@')

        return {
            'running_nodes': running_nodes_count,
            'is_partition': (partitions_count > 0),
        }

    def test_queue(self, cluster):
        # TODO pod に対してtestを行う
        exchange = Exchange('testex', type='direct')
        queue = Queue('testqueue', exchange=exchange, routing_key='test.health')
        start = time.time()
        try:
            with Connection(cluster['connection']) as c:
                bound = queue(c.default_channel)
                bound.declare()
                bound_exc = exchange(c.default_channel)
                msg = bound_exc.Message("hello")

                simple_queue = c.SimpleQueue(queue)
                msg = simple_queue.get(block=True, timeout=CONF.rabbitmq_manager.rpc_timeout)
                msg.ack()
        except Exception:
            LOG.error(traceback.format_exc())
            return False

        elapsed_time = time.time() - start
        LOG.info("Latency: {0}").format(elapsed_time)
        return True

    def destroy(self, name):
        LOG.error("Destroy {0}: {1}".format(name, self.cluster_map[name]))
        self.assign_services_to_cluster(ignore=name)
        util.execute('helm delete --tiller-namespace {0} --purge {1}'.format(CONF.rabbitmq_manager.tiller_namespace, name))
        self.cluster_map[name]['provisioning_status'] = -1
        self.cluster_map[name]['assigned_svc'] = None

    def assign_services_to_cluster(self, ignore=None):
        for svc_name, svc in self.svc_map.items():
            if svc['selector'] == 'none' or svc['selector'] == ignore:
                for cluster_name, cluster in self.cluster_map.items():
                    if cluster_name == ignore:
                        continue

                    if cluster['provisioing_status'] == 1 and cluster['assigned_svc'] is None:
                        util.execute("helm upgrade {0} --tiller-namespace {1} --set selector={2},transport_url='{4}'".format(
                            svc_name, CONF.rabbitmq_manager.tiller_namespace, cluster_name, svc['transport_url']))
                        cluster['assigned_svc'] = svc_name
                        svc['selector'] = cluster_name
                        break


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
