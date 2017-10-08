# coding: utf-8

import re
import time
import os
from lib import util
from oslo_config import cfg
from oslo_log import log


WATCH_DIR = os.environ.get('WATCH_DIR', '/mnt/openstack/bin')
WATCH_INTERVAL = int(os.environ.get('WATCH_INTERVAL', 10))
VALUES_FILE = '/mnt/openstack/etc/values.yaml'
RE_HELM_LIST = re.compile('^([a-zA-Z0-9\-]+)[ \t].*DEPLOYED[ \t]+([a-zA-Z0-9]+)-([0-9\.]+) .*$')

CONF = cfg.CONF
LOG = log.getLogger(__name__)


def main():
    LOG.info('start controller')
    file_map = {}
    resource_map = {}

    while True:
        # Execute bootstrap_files
        # When bootstarp_file is changed, execute bootstrap_file again.
        bootstrap_files = []
        for root, dirs, files in os.walk(WATCH_DIR):
            for file in files:
                if file.find('bootstrap-') == 0:
                    bootstrap_file = os.path.join(root, file)
                    bootstrap_files.append(bootstrap_file)

        bootstrap_files.sort()
        for bootstrap_file in bootstrap_files:
            bootstrap = file_map.get(bootstrap_file, {
                'current_hash': '',
            })
            tmp_hash = util.sha256(bootstrap_file)
            if tmp_hash != bootstrap['current_hash']:
                LOG.info('{0} is changed'.format(bootstrap_file))
                cmd = bootstrap_file
                result = util.execute(cmd)

                bootstrap['current_hash'] = tmp_hash
                file_map[bootstrap_file] = bootstrap

        # Check helm resources
        result = util.execute('helm list')

        # When values file is updated, update helm resources.
        tmp_hash = util.sha256(VALUES_FILE)
        tmp_file = file_map.get(VALUES_FILE, {
            'current_hash': '',
        })

        # When remote charts are updated, update helm resources.
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

        LOG.info('sleep {0}'.format(WATCH_INTERVAL))
        time.sleep(WATCH_INTERVAL)


if __name__ == '__main__':
    main()
