To install MariaDB with lower table names enabled, change the root password, and allow remote access, follow these steps:
Step 1: Install MariaDB

Install MariaDB on your server using your package manager. For example, if you're using Ubuntu, you can run the following command:

`sudo apt-get install mariadb-server`

Step 2: Enable Lower Table Names

By default, MariaDB is configured to use case-sensitive table names. To enable lower table names, you need to modify the configuration file. Here's how:

    Open the MariaDB configuration file /etc/mysql/mariadb.conf.d/50-server.cnf using your preferred text editor.
    Add the following line under the [mysqld] section:
    lower_case_table_names=1

Step 3: Change Root Password
For security reasons, you should change the root password of your MariaDB installation. Here's how:
    Log in to MariaDB as the root user by running the following command:

`sudo mariadb -u root`

Enter the following SQL command to change the root password:

`ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password';`

Replace new_password with your desired password.

Exit the MariaDB shell by running the following command:
    exit

Step 4: Allow Remote Access

By default, MariaDB only allows connections from localhost. If you want to allow remote access, you need to modify the MariaDB user account and the firewall. Here's how:

    Log in to MariaDB as the root user by running the following command:

`sudo mariadb -u root`

Enter the following SQL command to create a new user account:

`CREATE USER 'remote_user'@'%' IDENTIFIED BY 'password';`

Replace remote_user with the username you want to use and password with the password you want to use.

Grant the necessary privileges to the user by running the following command:

`GRANT ALL PRIVILEGES ON *.* TO 'remote_user'@'%';`
Exit the MariaDB shell by running the following command:
`exit`

Modify your firewall to allow incoming connections to port 3306 (the default port used by MariaDB). For example, if you're using UFW on Ubuntu, you can run the following command:
    sudo ufw allow from any to any port 3306 proto tcp
    This will allow incoming connections to port 3306 from any IP address.
That's it! You've now installed MariaDB with lower table names enabled, changed the root password, and allowed remote access.