# coding: utf-8

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

config.load_kube_config()
k8s_corev1api = client.CoreV1Api()

STATUS_NOT_INSTALLED = -1
STATUS_INSTALLED = 0
STATUS_ACTIVE = 1
STATUS_ACTIVE_ALL_GREEN = 2

TEST_QUEUE_NAME = 'testqueue'
TEST_EXCHANGE_NAME = 'testex'
TEST_ROUTING_KEY = 'test.health'
TEST_MSG = 'hello'


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
        self.k8s_services = {}
        self.k8s_pods = {}
        self.helm = helm.Helm()

        self.update_resource_map()

        # initialize cluster_map
        pool_count = len(CONF.rabbitmq_manager.services) + CONF.rabbitmq_manager.cluster_backups
        for id in range(pool_count):
            name = 'rabbitmq-cluster-{0}'.format(id)
            self.cluster_pool.add(name)
            self.init_cluster_data(name)

        # initialize svc_map
        for svc_vhost in CONF.rabbitmq_manager.services:
            name = 'rabbitmq-svc-{0}'.format(svc_vhost)
            self.svc_map[name] = {
                'provisioning_status': STATUS_NOT_INSTALLED,
                'vhost': svc_vhost,
                'selector': None,
            }

        # helm install svc_map
        for name, svc in self.svc_map.items():
            if name not in self.helm_resource_map:
                self.helm.install(name, 'rabbitmq-svc')
                svc['provisioning_status'] = STATUS_INSTALLED
            else:
                svc['provisioning_status'] = STATUS_ACTIVE
                selector = self.k8s_svc_map[name].spec.selector['app']
                if selector != 'none':
                    svc['selector'] = self.k8s_svc_map[name].spec.selector['app']

    def update_resource_map(self):
        self.helm_resource_map = {}
        self.k8s_svc_map = {}
        self.k8s_pods_map = {}

        self.rabbitmq_nodes = k8s_corev1api.list_node(
            label_selector=CONF.rabbitmq_manager.label_selector).items

        if len(self.rabbitmq_nodes) < 1:
            raise Exception('rabbitmq-nodes are not found')

        self.helm_resource_map = self.helm.get_resource_map()

        k8s_svcs = k8s_corev1api.list_namespaced_service(
            CONF.rabbitmq_manager.k8s_namespace).items

        k8s_pods = k8s_corev1api.list_namespaced_pod(
            CONF.rabbitmq_manager.k8s_namespace).items

        for k8s_pod in k8s_pods:
            app_label = k8s_pod.metadata.labels.get('app')
            if app_label is None:
                continue
            pods = self.k8s_pods_map.get(app_label, [])
            pods.append(k8s_pod)
            self.k8s_pods_map[app_label] = pods

        for k8s_svc in k8s_svcs:
            name = k8s_svc.metadata.name
            self.k8s_svc_map[name] = k8s_svc

            svc = self.svc_map.get(name)
            if svc is None:
                continue

            node_port = None
            for port in k8s_svc.spec.ports:
                if port.name == 'rabbitmq':
                    node_port = port.node_port
                    break

            transport_url = 'rabbit:\\\\/\\\\/'
            for node in self.rabbitmq_nodes:
                node_ip = None
                for address in node.status.addresses:
                    if address.type == 'InternalIP':
                        node_ip = address.address
                        break

                transport_url += "{0}:{1}@{2}:{3}\,".format(
                    self.user, self.password, node_ip, node_port
                )

            transport_url = transport_url[0:-2] + '\\\\/' + svc['vhost']
            svc['transport_url'] = transport_url

    def periodic_tasks(self, context, raise_on_error=False):
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(spacing=10)
    def check(self, context):
        LOG.info('Start check')
        self.update_resource_map()

        for name, cluster in self.cluster_map.items():
            if name not in self.helm_resource_map:
                self.helm.install(name, 'rabbitmq-cluster')
                cluster['provisioning_status'] = STATUS_INSTALLED
                continue

            pods = 0
            running_pods = 0
            running_nodes = 0
            unhealty_pods = 0
            failed_get_cluster_status = 0
            is_partition = False
            is_healty = True
            for pod in self.k8s_pods_map[name]:
                # if line.find('Error') > 1 or line.find('Crash') > 1:
                #     LOG.error('Pod is error, these node will be self.destroyed')
                #     self.destroy(name)

                pods += 1
                if not pod.status.phase == 'Running':
                    continue

                is_ready = True
                LOG.debug(pod.status)
                for cstatus in pod.status.container_statuses:
                    if not cstatus.ready:
                        is_ready = False
                        break
                if not is_ready:
                    unhealty_pods += 1
                    continue

                running_pods += 1

                cluster_status = self.get_cluster_status(pod)
                if cluster_status is None:
                    failed_get_cluster_status += 1

                if cluster_status['is_partition']:
                    is_partition = True
                    break

                running_nodes += cluster_status['running_nodes']

                self.test_queue(pod)

            if is_partition:
                self.destroy(name)
                continue

            # if running_pods >= 2 and not self.test_queue(cluster):
            #     self.destroy(name)
            #     continue

            if unhealty_pods != 0:
                is_healty = False
                cluster['warning']['exists_unhealty_pods'] += unhealty_pods
                destroy_threshold = CONF.rabbitmq_manager.wait_unhealty_pods_time / CONF.rabbitmq_manager.check_interval
                if cluster['provisioning_status'] < 1:
                    destroy_threshold = destroy_threshold * pods

                LOG.warning('Found unhealty_pods={0}, destroy_threshold={1}'.format(
                    cluster['warning']['exists_unhealty_pods'],
                    destroy_threshold
                ))
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

        self.assign_services_to_cluster()
        LOG.info("Check Summary")
        for cluster_name, cluster in self.cluster_map.items():
            LOG.info("{0}: {1}".format(cluster_name, cluster))

    def get_cluster_status(self, pod):
        pod_name = pod.metadata.name
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

    def test_queue(self, pod):
        connection = 'amqp://{0}:{1}@{2}:5672/test'.format(
            self.user, self.password, pod.status.pod_ip)
        exchange = Exchange(TEST_EXCHANGE_NAME, type='direct')
        queue = Queue(TEST_QUEUE_NAME, exchange=exchange, routing_key=TEST_ROUTING_KEY)
        start = time.time()
        try:
            with Connection(connection) as c:
                bound = queue(c.default_channel)
                bound.declare()
                bound_exc = exchange(c.default_channel)
                msg = bound_exc.Message(TEST_MSG)
                bound_exc.publish(msg, routing_key=TEST_ROUTING_KEY)

                simple_queue = c.SimpleQueue(queue)
                msg = simple_queue.get(block=True, timeout=CONF.rabbitmq_manager.rpc_timeout)
                msg.ack()
        except Exception:
            LOG.error(traceback.format_exc())
            return False

        elapsed_time = time.time() - start

        LOG.info("Latency: {0}".format(elapsed_time))
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        metrics_map['rabbitmq_msg_latency'] = {
            'tags': {"pod": pod.metadata.name, "deployment": pod.metadata.labels['app']},
            'value': elapsed_time,
            'time': timestamp,
        }
        return True

    def init_cluster_data(self, name):
        self.cluster_map[name] = {
            'provisioning_status': STATUS_NOT_INSTALLED,
            'assigned_svc': None,
            'warning': {
                'exists_unhealty_pods': 0,
                'exists_standalone_nodes': 0,
                'failed_get_cluster_status': 0,
            }
        }

    def destroy(self, name):
        LOG.error("Destroy {0}: {1}".format(name, self.cluster_map[name]))
        self.assign_services_to_cluster(ignore=name)
        self.helm.delete(name)
        self.init_cluster_data(name)

    def assign_services_to_cluster(self, ignore=None):
        for svc_name, svc in self.svc_map.items():
            if svc['selector'] == 'none' or svc['selector'] == ignore:
                for cluster_name, cluster in self.cluster_map.items():
                    if cluster_name == ignore:
                        continue

                    if cluster['provisioning_status'] >= STATUS_ACTIVE and cluster['assigned_svc'] is None:
                        option = "--set selector={0},transport_url='{1}'".format(
                            cluster_name, svc['transport_url'])
                        self.helm.upgrade(svc_name, 'rabbitmq-svc', option)
                        cluster['assigned_svc'] = svc_name
                        svc['selector'] = cluster_name
                        break


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
