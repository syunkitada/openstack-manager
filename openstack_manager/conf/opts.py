# coding: utf-8

import itertools
from oslo_config import cfg, types

CONF = cfg.CONF
PortType = types.Integer(1, 65535)


k8s_opts = [
    cfg.StrOpt(
        'namespace',
        default='openstack',
        help='namespace'),
    cfg.StrOpt(
        'tiller_namespace',
        default='kube-system',
        help='tiller_namespace'),
    cfg.StrOpt(
        'chart_repo_prefix',
        default='/home/fabric/openstack-helm',
        help='chart_repo_prefix'),
    cfg.StrOpt(
        'values_file',
        default='/mnt/openstack/etc/values.yaml',
        help='values_file path'),

]

openstack_auth_opts = [
    cfg.StrOpt(
        'auth_url',
        default='https://keystone-public.k8s.example.com/v3',
        help='auth_url'),
    cfg.StrOpt(
        'username',
        default='admin',
        help='username of service account'),
    cfg.StrOpt(
        'password',
        default='adminpass',
        help='password of service account'),
    cfg.StrOpt(
        'project_name',
        default='admin',
        help='project name'),
    cfg.StrOpt(
        'user_domain_id',
        default='default',
        help='user domain_id'),
    cfg.StrOpt(
        'project_domain_id',
        default='default',
        help='project domain_id'),
]

influxdb_opts = [
    cfg.BoolOpt(
        'enable',
        default=True,
        help='enable to report influxdb'),
    cfg.StrOpt(
        'host',
        default='monitoring-influxdb.kube-system.svc.cluster.local',
        help='influxdb host'),
    cfg.Opt(
        'port',
        type=PortType,
        default=8086,
        help='influxdb port'),
    cfg.StrOpt(
        'user',
        default='root',
        help='influxdb user'),
    cfg.StrOpt(
        'password',
        default='rootpass',
        help='influxdb password'),
    cfg.StrOpt(
        'database',
        default='openstack',
        help='influxdb database'),
]

openstack_deploy_manager_opts = [
    cfg.BoolOpt(
        'enable_prometheus_exporter',
        default=True,
        help='enable prometheus_exporter'),
    cfg.StrOpt(
        'prometheus_exporter_bind_host',
        default='0.0.0.0',
        help='IP address to listen on for prometheus_exporter'),
    cfg.Opt(
        'prometheus_exporter_bind_port',
        type=PortType,
        default=19201,
        help='Port number to listen on for prometheus_exporter'),
    cfg.IntOpt(
        'check_interval',
        default=20,
        help='check_interval'),
    cfg.StrOpt(
        'bin_dir',
        default='/mnt/openstack/bin',
        help='dir_dir'),
    cfg.StrOpt(
        'upgrade_values_sh',
        default='/mnt/openstack/bin/upgrade_values.sh',
        help='upgrade_values_sh path'),
]

openstack_monitor_manager_opts = [
    cfg.BoolOpt(
        'enable_prometheus_exporter',
        default=True,
        help='enable prometheus_exporter'),
    cfg.StrOpt(
        'prometheus_exporter_bind_host',
        default='0.0.0.0',
        help='IP address to listen on for prometheus_exporter'),
    cfg.Opt(
        'prometheus_exporter_bind_port',
        type=PortType,
        default=19202,
        help='Port number to listen on for prometheus_exporter'),
]

rabbitmq_manager_opts = [
    cfg.BoolOpt(
        'enable_prometheus_exporter',
        default=True,
        help='enable prometheus_exporter'),
    cfg.StrOpt(
        'prometheus_exporter_bind_host',
        default='0.0.0.0',
        help='IP address to listen on for prometheus_exporter'),
    cfg.Opt(
        'prometheus_exporter_bind_port',
        type=PortType,
        default=19203,
        help='Port number to listen on for prometheus_exporter'),
    cfg.IntOpt(
        'check_interval',
        default=20,
        help='check_interval'),
    cfg.IntOpt(
        'wait_unhealty_pods_time',
        default=600,
        help='wait_unhealty_pods_interval'),
    cfg.StrOpt(
        'user',
        default='openstack',
        help='rabbitmq user'),
    cfg.StrOpt(
        'password',
        default='openstackpass',
        help='rabbitmq password'),
    cfg.ListOpt(
        'services',
        default=['common'],
        help='services'),
    cfg.IntOpt(
        'cluster_backups',
        default=1,
        help='backups'),
    cfg.IntOpt(
        'rpc_timeout',
        default=10,
        help='rpc_timeout'),
    cfg.StrOpt(
        'node_label_selector',
        default='rabbitmq-node=enable',
        help='chart_repo_prefix'),
]


def list_opts():
    return [
        ('k8s', itertools.chain(k8s_opts)),
        ('influxdb', itertools.chain(influxdb_opts)),
        ('openstack_auth', itertools.chain(openstack_auth_opts)),
        ('openstack_deploy_manager', itertools.chain(openstack_deploy_manager_opts)),
        ('openstack_monitor_manager', itertools.chain(openstack_monitor_manager_opts)),
        ('rabbitmq_manager', itertools.chain(rabbitmq_manager_opts)),
    ]
