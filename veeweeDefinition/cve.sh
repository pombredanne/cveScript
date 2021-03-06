export LANGUAGE=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
locale-gen en_US.UTF-8
dpkg-reconfigure locales

##mongo
apt-get update
apt-get -y install mongodb

##redis
apt-get -y install build-essential
apt-get -y install tcl8.5
apt-get -y install redis-server

##pip3
apt-get -y install python-dev 
apt-get -y install libxml2-dev 
apt-get -y install libxslt1-dev 
apt-get -y install zlib1g-dev
apt-get -y install python3-pip
apt-get -y install libffi-dev

##nmap
apt-get -y install nmap

##git
apt-get -y install git

cd ~
mkdir git
cd git
git clone https://github.com/CIRCL/cve-portal.git
git clone https://github.com/NorthernSec/CVE-Scan.git
git clone https://github.com/cve-search/cve-search.git


##cve-search
cd cve-search
cd etc
cp configuration.ini.sample configuration.ini
cd ..
###need to activate fulltext search on mongodb
echo "setParameter=textSearchEnabled=true" >> /etc/mongodb.conf
service mongodb restart
###
pip3 install -r requirements.txt
python3 ./sbin/db_mgmt_create_index.py
python3 ./sbin/db_mgmt.py -p
python3 ./sbin/db_mgmt_cpe_dictionary.py
python3 ./sbin/db_mgmt_cpe_other_dictionary.py
python3 ./sbin/db_updater.py -c

##PORTAL not working correctly
#apt-get install -y mysql-server
#apt-get install -y postfix
cd ~/git/cve-portal/app
./install.sh
###how to modify the file?
cp config/config.cfg.sample config/config.cfg
###modify config esto se va a descontrolar :v
###. ./virtenv/bin/activate

##SCAN
cd ~/git/CVE-Scan/
pip3 install -r requirements.txt 


cd

##WEB Services
# python3 ./git/cve-search/web/index.py

##Run a scan
# nmap -A -O localhost -oX output.xml
# python3 ./git/CVE-Scan/bin/Nmap2CVE-Search.py output.xml 
