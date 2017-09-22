#!/bin/sh

prefix=/opt/openstack_sample
[ -e $prefix ] || virtualenv $prefix

$prefix/bin/pip install -r requirements.txt
$prefix/bin/pip install -r test-requirements.txt

$prefix/bin/python setup.py develop

tox -egenconfig
mkdir -p /etc/openstack_sample/
[ -e /etc/openstack_sample/openstack_sample.conf ] || cp etc/openstack_sample.conf.sample /etc/openstack_sample/openstack_sample.conf
