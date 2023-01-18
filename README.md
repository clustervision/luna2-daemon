# luna2-daemon

Luna 2 Daemon is a part of the Luna 2 Project.
Luna 2 Daemon is a daemon with Microservices(REST API). 
It will use TCP/IP connectivity port 7050 as the default.

## Installation

Currently the Installation is tested only on CentOS 8 & 9 ARCH=64.

* Install Required Packages
Included ODBC Driver Managr, PostgreSQL Server & ODBC Driver, MySQL Server, SQLite, Git and OpenSSL
```
yum -y groupinstall "Development Tools"
dnf install -y wget yum-utils make gcc openssl-devel bzip2-devel libffi-devel zlib-devel \
				git sqlite-devel unixODBC unixODBC-devel mysql-server postgresql-server postgresql-odbc
```

** In case of unavailability of any package find & installation process -> https://pkgs.org/
* Install Python 3.10
```
wget https://www.python.org/ftp/python/3.10.8/Python-3.10.8.tgz -P /opt/
tar xzf /opt/Python-3.10.8.tgz --directory /opt/
cd /opt/Python-3.10.8 && ./configure --enable-loadable-sqlite-extensions --enable-optimizations
make -j8
make install
ln -fs /usr/local/bin/python3.10  /bin/python
ln -fs /usr/local/bin/pip3.10 /bin/pip
ln -fs /usr/local/bin/pip3.10 /usr/local/bin/pip
pip install --upgrade pip
```
* Install SQLite ODBC Driver
```
wget http://www.ch-werner.de/sqliteodbc/sqliteodbc-0.9998.tar.gz -P /opt/
tar xvf /opt/sqliteodbc-0.9998.tar.gz --directory /opt/
cd /opt/sqliteodbc-0.9998 && ./configure
make -j8
make install
```
* Install MySQL ODBC Driver
```
systemctl start mysqld
systemctl enable  mysqld
sudo mysql_secure_installation # Setup Username and Password
Validate Password Component: y
Security Level: 0
Password: luna@123
Retype Password: luna@123
Confirm With Password: y
Remove anonymous: y
Disallow remote login: n
remove test database: y
reload privillages: y
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


mkdir /trinity
mkdir /trinity/local
git clone -c http.sslVerify=false https://gitlab.taurusgroup.one/clustervision/luna2-daemon.git /trinity/local/luna
Username: sumit
password: *********
cd /trinity/local/luna && git checkout development
cp /trinity/local/luna/config/odbcinst.ini /etc/odbcinst.ini
pip install -r /trinity/local/luna/requirements.txt

mkdir /trinity/local/etc
mkdir /trinity/local/etc/ssl
echo 'CwSQcHNqiLSHXQaCDtAF2414e3muXgmpht6ocVA2xGs=' > /trinity/local/etc/ssl/luna.key

mkdir /trinity/local/luna/log
touch /trinity/local/luna/log/luna2-daemon.log

cp /trinity/local/luna/config/luna2-daemon.service /etc/systemd/system/
setenforce 0
firewall-cmd --zone=public --permanent --add-port 7050/tcp
firewall-cmd --reload
systemctl status luna2-daemon.service
systemctl enable luna2-daemon.service
```
http://127.0.0.1:7050
