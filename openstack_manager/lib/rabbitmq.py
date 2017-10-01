#!/usr/bin/env python
# coding: utf-8

import re
import subprocess
import time
import hashlib
import os
import util

LOG = util.getLog(__name__)
WATCH_INTERVAL = int(os.environ.get('WATCH_INTERVAL', 10))
SERVICES = os.environ.get('SERVICES', 'common').split(',')
BUCKUPS = int(os.environ.get('BUCKUPS', 1))
POOL_COUNT = len(SERVICES) + BUCKUPS
NAMESPACE = os.environ.get('NAMESPACE', '{{ .Release.Namespace }}')
REPO_PREFIX = '/home/fabric/openstack-helm'
# RE_HELM_LIST = re.compile('^([a-zA-Z0-9\-]+)[ \t]+[\d]+[ \t]+.* [\d]+ [ \t]+([A-Z]+)[ \t]+([a-zA-Z0-9]+)-([0-9\.]+) .*$')
RE_HELM_LIST = re.compile('^([a-zA-Z0-9\-]+)[ \t]+([\d]+)[ \t]+.*[ \t]+([A-Z]+)[ \t]+([a-zA-Z0-9\-]+)-([0-9\.]+)[ \t]+.*')
VALUES_FILE = '/mnt/rabbitmq/etc/values.yaml'
WAIT_UNHEALTY_PODS_TIME = 360
cluster_pool = set()
cluster_map = {}
svc_map = {}
helm_resource_map = {}


def main():
    LOG.info('start controller')
    bootstrap()

    while True:
        LOG.info('Start management rabbitmq clusters')
        manage_rabbitmq()

        LOG.info('Sleep {0}'.format(WATCH_INTERVAL))
        time.sleep(WATCH_INTERVAL)


def manage_rabbitmq():
    update_helm_resource_map()
    print helm_resource_map

    for name, svc in svc_map.items():
        if name not in helm_resource_map:
            util.execute('helm install --name {0} {1}/rabbitmq-svc'.format(
                name, REPO_PREFIX
            ))
            svc['provisioning_status'] = 0
        else:
            svc['provisioning_status'] = 1
            result = util.execute("kubectl get svc {0} -o jsonpath='{{.spec.selector.app}}'".format(name))
            selector = result['stdout']
            svc_map[name]['selector'] = selector
            svc_map[name]['transport_url'] = ''

    for name, cluster in cluster_map.items():
        if name not in helm_resource_map:
            util.execute('helm install --name {0} {1}/rabbitmq-cluster -f {2}'.format(
                name, REPO_PREFIX, VALUES_FILE
            ))
            cluster['provisioning_status'] = 0
        else:
            cluster['provisioning_status'] = 1

        result = util.execute('kubectl get pod -l app={0}'.format(name))
        pods = 0
        running_pods = 0
        running_nodes = 0
        unhealty_pods = 0
        failed_get_cluster_status = 0
        is_partition = False
        is_healty = True
        for line in result['stdout'].split('\n'):
            if line.find('Error') > 1 or line.find('Crash') > 1:
                LOG.error('Pod is error, these node will be destroyed')
                destroy(name)

            pods += 1
            if line.find('Running') == -1:
                continue
            if line.find(' 1/1 ') == -1:
                unhealty_pods += 1
                continue

            running_pods += 1

            pod = line.split(' ', 1)[0]
            cluster_status = get_cluster_status(pod)
            if cluster_status is None:
                failed_get_cluster_status += 1

            if cluster_status['is_partition']:
                is_partition = True
                break

            running_nodes += cluster_status['running_nodes']

        if is_partition:
            destroy(name)
            continue

        if running_pods >= 2 and not test_queue(cluster):
            destroy(name)
            continue

        if unhealty_pods != 0:
            is_healty = False
            LOG.warning('Found unhealty_pods')
            cluster['warning']['exists_unhealty_pods'] += unhealty_pods
            destroy_threshold = pods * (WAIT_UNHEALTY_PODS_TIME / WATCH_INTERVAL)
            if cluster['warning']['exists_unhealty_pods'] >= destroy_threshold:
                destroy(name)
        else:
            cluster['warning']['exists_unhealty_pods'] = 0

            standalone_pods = (running_pods * running_pods) - running_nodes
            if standalone_pods != 0:
                is_healty = False
                LOG.warning('Found standalone_pods')
                cluster['warning']['exists_standalone_nodes'] += 1
                if cluster['warning']['exists_standalone_nodes'] >= 2:
                    destroy(name)
            else:
                cluster['warning']['exists_standalone_nodes'] = 0

            if failed_get_cluster_status != 0:
                is_healty = False
                LOG.warning('Failed get cluster_status')
                cluster['warning']['failed_get_cluster_status'] += 1
                if cluster['warning']['failed_get_cluster_status'] >= 2:
                    destroy(name)
            else:
                cluster['warning']['failed_get_cluster_status'] = 0

            if is_healty:
                cluster['provisioning_status'] = 1

    assign_services_to_cluster()


def get_cluster_status(pod_name):
    cluster_status = util.execute('kubectl exec {0} rabbitmqctl cluster_status'.format(pod_name),
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


def test_queue(cluster):
    print cluster
    return True


def destroy(name):
    LOG.info("Destroy {0}".format(name))
    assign_services_to_cluster(ignore=name)
    util.execute('helm delete --purge {0}'.format(name))
    cluster_map['name']['provisioning_status'] = -1
    cluster_map['name']['assigned_svc'] = None


def assign_services_to_cluster(ignore=None):
    for svc_name, svc in svc_map.items():
        if svc['selector'] == 'none' or svc['selector'] == ignore:
            for cluster_name, cluster in cluster_map:
                if cluster_name == ignore:
                    continue

                if cluster['provisioing_status'] == 1 and cluster['assigned_svc'] is None:
                    util.execute('helm upgrade {0} --set selector={1}'.format(
                        svc_name, cluster_name))
                    cluster['assigned_svc'] = svc_name
                    svc['selector'] = cluster_name
                    break


def update_helm_resource_map():
    global helm_resource_map
    helm_resource_map = {}
    result = util.execute('helm list')
    for line in result['stdout'].split('\n'):
        m = RE_HELM_LIST.match(line)
        if m is None:
            continue

        resource_name = m.group(1)
        revision = m.group(2)
        status = m.group(3)
        chart = m.group(4)
        version = m.group(5)

        helm_resource_map[resource_name] = {
            'revision': revision,
            'status': status,
            'chart': chart,
            'version': version,
        }


def bootstrap():
    user = 'openstack'
    password = 'openstackpass'

    for id in range(POOL_COUNT):
        name = 'rabbitmq-cluster-{0}'.format(id)
        cluster_pool.add(name)
        cluster_map[name] = {
            'provisioning_status': -1,
            'assigned_svc': None,
            'connection': 'amqp://{0}:{1}@{2}:5672/test'.format(user, password, name),
            'warning': {
                'exists_unhealty_pods': 0,
                'exists_standalone_nodes': 0,
                'failed_get_cluster_status': 0,
            }
        }

    for service in SERVICES:
        name = 'rabbitmq-svc-{0}'.format(service)
        svc_map[name] = {
            'provisioning_status': -1,
            'vhost': '{0}'.format(service),
            'selector': None,
        }


if __name__ == '__main__':
    main()
