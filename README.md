# luna2-daemon

Luna 2 Daemon is a part of the Luna 2 Project.
Luna 2 Daemon is a daemon with Microservices(REST API). 
It will use TCP/IP connectivity port 7050 as the default.

## Installation

Currently the Installation is tested only on CentOS 8 & 9 ARCH=64.

* Install Required Packages
Included ODBC Driver Managr, PostgreSQL Server & ODBC Driver, MySQL Server, SQLite, Git and OpenSSL
```
dnf install -y wget yum-utils make gcc openssl-devel bzip2-devel libffi-devel zlib-devel \
				git sqlite-devel unixODBC unixODBC-devel mysql-server postgresql-server \
				postgresql-odbc
				```

** In case of unavailability of any package find & installation process -> https://pkgs.org/
* Install Python 3.10
```
wget https://www.python.org/ftp/python/3.10.7/Python-3.10.7.tgz -P /opt/
tar xzf /opt/Python-3.10.7.tgz --directory /opt/Python-3.10.7
./opt/Python-3.10.7/configure --enable-loadable-sqlite-extensions --enable-optimizations
make -j8
make install
ln -fs /usr/local/bin/python3.10  /bin/python
ln -fs /usr/local/bin/pip3.10 /bin/pip
```
* Install SQLite ODBC Driver
```
wget http://www.ch-werner.de/sqliteodbc/sqliteodbc-0.9998.tar.gz -P /opt/
tar xvf sqliteodbc-0.9998.tar.gz --directory /opt/sqliteodbc-0.9998
./opt/sqliteodbc-0.9998/configure
make -j8
make install
```
* Install MySQL ODBC Driver
```
sudo mysql_secure_installation # Setup Username and Password
wget https://repo.mysql.com/yum/mysql-connectors-community/el/8/x86_64/mysql-connector-odbc-8.0.30-1.el8.x86_64.rpm -P /opt/
wget https://repo.mysql.com/yum/mysql-connectors-community/el/8/x86_64/mysql-connector-odbc-setup-8.0.30-1.el8.x86_64.rpm -P /opt/
yum install /opt/mysql-connector-odbc-8.0.30-1.el8.x86_64.rpm
yum install /opt/mysql-connector-odbc-setup-8.0.30-1.el8.x86_64.rpm
```
* Install PostgreSQL ODBC Driver
```
postgresql-setup --initdb
systemctl enable --now postgresql
su - postgres # Create User and Password and assign the role
odbcinst -q -d # Check and update ODBC Driver's Configuration OR Refer to /trinity/local/luna/config/odbcinst.ini
```
* Clone & Run Luna 2 Daemon
```
git clone https://gitlab.taurusgroup.one/clustervision/luna2-daemon.git /trinity/local/luna
pip -r install /trinity/local/luna/requirements.txt
./trinity/local/luna/setup.py # It will create & start Luna2-Daemon systemd service.
```
http://127.0.0.1:7050
