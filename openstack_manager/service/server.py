# coding: utf-8

import threading
from oslo_config import cfg
from oslo_log import log
from oslo_service import service
import wsgi_app

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class APIService(service.Service):
    def __init__(self, name='openstack_manager'):
        super(APIService, self).__init__()

    def start(self):
        LOG.info('start')
        wsgi_app.init()
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

        super(APIService, self).stop()

    def periodic_tasks(self, raise_on_error=False):
        ctxt = {}
        return wsgi_app.periodic_manager.periodic_tasks(ctxt, raise_on_error=raise_on_error)

    def spawn_app(self):
        # t = threading.Thread(target=wsgi_app.run, args=args, kwargs=kwargs)

        t = threading.Thread(target=wsgi_app.wsgi_app.run, kwargs={
            'host': CONF.openstack_manager.bind_host,
            'port': CONF.openstack_manager.bind_port
        })
        t.daemon = True
        t.start()
        return t


def launch():
    launcher = service.launch(CONF, APIService())
    launcher.wait()
