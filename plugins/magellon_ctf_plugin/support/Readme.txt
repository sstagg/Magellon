https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html

http://localhost:5601
https://localhost:9200/

GET _cat/indices
GET sales/_search

docker-compose up -d
docker-compose down
docker-compose down -v

.\filebeat.exe -c filebeat.yml -e -d "*"

## grafana
dashboars and datasources are in sqlite database now
docker-compose exec grafana bash

http://127.0.0.1:9090
http://localhost:3000

/usr/share/grafana/public/dashboards/home. json
ls /var/lib/grafana/
cd /etc/grafana/

GF_PATHS_CONFIG	/etc/grafana/grafana.ini
GF_PATHS_DATA	/var/lib/grafana
GF_PATHS_HOME	/usr/share/grafana
GF_PATHS_LOGS	/var/log/grafana
GF_PATHS_PLUGINS	/var/lib/grafana/plugins
GF_PATHS_PROVISIONING	/etc/grafana/provisioning


### MySql
sudo docker exec -i -t 665b4a1e17b6 /bin/bash

SHOW VARIABLES LIKE 'lower_case_table_names';


docker logs rabbitmq-container