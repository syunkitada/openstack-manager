#!/bin/bash -xe

yum install -y gcc python-devel
easy_install pip
pip install virtualenv
[ -e /opt/openstack-manager ] || sudo virtualenv /opt/openstack-manager
/opt/openstack-manager/bin/pip install -r requirements.txt
pip install -r test-requirements.txt

/opt/openstack-manager/bin/python setup.py develop

tox -egenconfig
mkdir -p /etc/openstack_manager
cp etc/openstack_manager.conf.sample /etc/openstack_manager/openstack_manager.conf

mkdir -p /mnt/openstack/etc/
cp /home/${SUDO_USER}/openstack-helm/openstack/values.yaml /mnt/openstack/etc/


cat <<EOS > /home/${SUDO_USER}/.kube/config
apiVersion: v1
clusters:
- cluster:
    server: http://127.0.0.1:8080
  name: default
contexts:
- context:
    cluster: default
    user: admin
    namespace: openstack
  name: default
current-context: default
kind: Config
preferences: {}
users:
- name: admin
  user:
    username: admin
    password: password
EOS
