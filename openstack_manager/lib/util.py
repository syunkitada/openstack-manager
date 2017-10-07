# coding: utf-8

import hashlib
import os
import stat
import subprocess
from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF
LOG = log.getLogger(__name__)


def execute(cmd, is_chmod=False, enable_exception=True):
    msg = "bash: {0}".format(cmd)
    if is_chmod:
        os.chmod(cmd[0], stat.S_IXUSR)
    LOG.info(msg)

    p = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = ''
    while True:
        line = p.stdout.readline()
        LOG.debug(line[:-1])
        stdout += line
        if not line and p.poll() is not None:
            break

    return_code = p.wait()
    stderr = p.stderr.read().decode('utf-8')

    p.stdout.close()
    p.stderr.close()

    msg = "bash: {0}, return_code: {1}\n  stderr: {2}\n".format(cmd, return_code, stderr)
    LOG.info(msg)
    if enable_exception:
        if return_code != 0:
            raise Exception('Failed cmd: {0}'.format(cmd))

    return {
        'return_code': return_code,
        'stdout': stdout,
        'stderr': stderr,
    }


def sha256(filename):
    hash_sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()
