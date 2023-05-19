


`apt install python3 python3-pip

pip3 install apache-airflow
airflow db init
airflow webserver
airflow webserver -p 808

airflow scheduler



cd ~/airflow/dags    # for Linux and macOS
cd  /root/airflow/dags

airflow users  create --role Admin --username admin --email admin --firstname admin --lastname admin --password admin


https://towardsdatascience.com/a-complete-introduction-to-apache-airflow-b7e238a33df