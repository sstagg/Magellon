#!/bin/bash

# Load configuration file
source ./config.sh

# Check if MariaDB is installed
if command -v mariadb &> /dev/null
then
    echo "MariaDB is already installed"
else
    # Install MariaDB based on the current operating system
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # Install on macOS using Homebrew
        echo "Installing MariaDB on macOS"
        brew install mariadb
    elif [[ "$(cat /etc/os-release | grep ID)" == *"debian"* ]]; then
        # Install on Debian-based systems using apt-get
        echo "Installing MariaDB on Debian"
        apt-get update
        apt-get install -y mariadb-server
    elif [[ "$(cat /etc/os-release | grep ID)" == *"centos"* ]] || [[ "$(cat /etc/os-release | grep ID)" == *"rhel"* ]]; then
        # Install on CentOS/RHEL-based systems using yum
        echo "Installing MariaDB on CentOS/RHEL"
        yum install -y mariadb-server
    else
        echo "Error: unsupported operating system"
        exit 1
    fi

    # Set lowercase table names in MariaDB configuration
    if ! grep -q "^lower_case_table_names" /etc/my.cnf; then
        echo "lower_case_table_names=1" >> /etc/my.cnf
    fi


  # Set lower_case_table_names
  echo "[mysqld]" | sudo tee -a /etc/my.cnf.d/mariadb-server.cnf > /dev/null
  echo "lower_case_table_names=1" | sudo tee -a /etc/my.cnf.d/mariadb-server.cnf > /dev/null


    # Enable and start MariaDB service
    systemctl enable mariadb
    systemctl start mariadb

    # Add a new user with all permissions
    mysql -u root <<EOF
    CREATE USER '$MYSQL_USER'@'%' IDENTIFIED BY '$MYSQL_PASSWORD';
    GRANT ALL PRIVILEGES ON *.* TO '$MYSQL_USER'@'%' WITH GRANT OPTION;
    FLUSH PRIVILEGES;
EOF

fi
