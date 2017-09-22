# coding: utf-8

import threading
import oslo_messaging
from oslo_config import cfg
from oslo_log import log
from oslo_service import service

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class ServerControlEndpoint(object):
    target = oslo_messaging.Target(namespace='control',
                                   version='2.0')

    def __init__(self, server):
        self.server = server

    def stop(self, ctx):
        if self.server:
            self.server.stop()


class TestEndpoint(object):
    target = oslo_messaging.Target(version='2.0')

    def test(self, ctx, arg):
        LOG.info('DEBUG')
        return arg


class APIService(service.Service):
    def __init__(self, name='openstack_sample'):
        super(APIService, self).__init__()

    def start(self):
        LOG.info('start')

        transport = oslo_messaging.get_transport(CONF)
        target = oslo_messaging.Target(topic=CONF.openstack_sample.topic,
                                       server=CONF.openstack_sample.host)
        endpoints = [
            ServerControlEndpoint(None),
            TestEndpoint(),
        ]
        self.server = oslo_messaging.get_rpc_server(
            transport, target, endpoints, executor='threading')

        self.server.start()

        self.udp_thread = self.spawn_app()

    def wait(self):
        LOG.info('wait')

    def stop(self):
        LOG.info('stop')

        if self.udp_thread:
            self.udp_thread.join()

        super(APIService, self).stop()

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)
        from wsgi_app import wsgi_app

        t = threading.Thread(target=wsgi_app.run, kwargs={
            'host': CONF.openstack_sample.bind_host,
            'port': CONF.openstack_sample.bind_port
        })
        t.daemon = True
        t.start()
        return t


def launch():
    launcher = service.launch(CONF, APIService())
    launcher.wait()
