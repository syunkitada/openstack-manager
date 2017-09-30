vip=172.16.100.130
domain=glance.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=grafana.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=horizon.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=keystone-admin.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=keystone-public.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=neutron.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=nova.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=placement.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
domain=prometheus.k8s.example.com
grep "$vip $domain" /etc/hosts || echo "$vip $domain" >> /etc/hosts
