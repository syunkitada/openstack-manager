#!/bin/bash -xe

yum install -y gcc python-devel
easy_install pip
pip install virtualenv
[ -e /opt/openstack-manager ] || sudo virtualenv /opt/openstack-manager
/opt/openstack-manager/bin/pip install -r requirements.txt
pip install -r test-requirements.txt

tox -egenconfig
mkdir -p /etc/openstack_manager
cp etc/openstack_manager.conf.sample /etc/openstack_manager/openstack_manager.conf

/opt/openstack-manager/bin/python setup.py develop
