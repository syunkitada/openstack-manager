# openstack-manager
* openstackの管理用コンポーネント群です


## コンポーネント
* k8s-openstack-deploy-manager
    * k8s上にopenstack-helmを利用してのopenstackのデプロイを行います
    * values, chartリソースが更新された場合に自動でアップグレードを行います
* k8s-openstack-monitor-manager
    * k8s上のopenstackを監視、各リソースメトリクスの収集を行います
* k8s-rabbitmq-manager
    * k8s上にrabbitmqをデプロイし、rabbitmqを監視、各リソースメトリクスの収集を行います
* openstack-monitor-manager
    * openstackの各リソースメトリクスの収集を行います


## メトリクス収集のバックエンド
* prometheus
    * optionでexporter機能を有効にできます
* influxdb
    * optionでinfluxdbへのレポート機能を有効にできます
    * optionでレポート先のinfluxdbを指定してください
