# coding: utf-8

import os
import stat
import subprocess
from logging import getLogger, StreamHandler, DEBUG, Formatter


def getLog(name):
    LOG_LEVEL = os.environ.get('LOG_LEVEL', DEBUG)
    logger = getLogger(name)
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = StreamHandler()
    handler.setLevel(DEBUG)
    handler.setFormatter(formatter)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)
    return logger


LOG = getLog(__name__)


def execute(cmd, is_chmod=False, enable_exception=True):
    msg = "bash: {0}".format(cmd)
    if is_chmod:
        os.chmod(cmd[0], stat.S_IXUSR)
    LOG.info(msg)

    p = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = ''
    while True:
        line = p.stdout.readline()
        LOG.info(line[:-1])
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
