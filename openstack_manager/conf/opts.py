# coding: utf-8

import itertools
from oslo_config import cfg, types

CONF = cfg.CONF
PortType = types.Integer(1, 65535)


openstack_manager_opts = [
    cfg.StrOpt('topic',
               default='openstack_sample',
               help='topic'),
    cfg.StrOpt('host',
               default='localhost',
               help='host'),
    cfg.StrOpt('bind_host',
               default='0.0.0.0',
               help='IP address to listen on'),
    cfg.Opt('bind_port',
            type=PortType,
            default=19999,
            help='Port number to listen on'),
    cfg.BoolOpt('enable_influxdb',
                default=True,
                help='Port number to listen on'),
]


rabbitmq_manager_opts = [
    cfg.StrOpt('bind_host',
               default='0.0.0.0',
               help='IP address to listen on'),
    cfg.Opt('bind_port',
            type=PortType,
            default=19998,
            help='Port number to listen on'),
    cfg.IntOpt('check_interval',
               default=20,
               help='check_interval'),
    cfg.IntOpt('wait_unhealty_pods_time',
               default=300,
               help='wait_unhealty_pods_interval'),
    cfg.StrOpt('user',
               default='openstack',
               help='rabbitmq user'),
    cfg.StrOpt('password',
               default='openstackpass',
               help='rabbitmq password'),
    cfg.ListOpt('services',
                default=['common'],
                help='services'),
    cfg.IntOpt('cluster_backups',
               default=1,
               help='backups'),
    cfg.StrOpt('k8s_namespace',
               default='openstack',
               help='k8s_namespace'),
    cfg.StrOpt('values_file_path',
               default='/home/fabric/openstack-helm/openstack/values.yaml',
               help='values_file_path'),
    cfg.StrOpt('tiller_namespace',
               default='kube-system',
               help='tiller_namespace'),
    cfg.StrOpt('chart_repo_prefix',
               default='/home/fabric/openstack-helm',
               help='chart_repo_prefix'),
    cfg.IntOpt('rpc_timeout',
               default=10,
               help='rpc_timeout'),
    cfg.StrOpt('label_selector',
               default='rabbitmq-node=enable',
               help='chart_repo_prefix'),

]


def list_opts():
    return [
        ('openstack_manager', itertools.chain(openstack_manager_opts)),
        ('rabbitmq_manager', itertools.chain(rabbitmq_manager_opts)),
    ]
