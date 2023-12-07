#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export ROOT_DIR=${SCRIPT_DIR}/..
export $(cat ${ROOT_DIR}/.env | grep -v '^#' | grep -v '^\s*$' | sed 's/\${\([^}]*\)}/\$\1/g' | xargs)
cd $ROOT_DIR

if [ $USER = $POSTGRES_USER ]; then
    psql="psql"
else
    psql="sudo -u $POSTGRES_USER psql"
fi

if [ -z $DATABASE ]; then
    echo "DATABASE variable not set - exiting"
    exit 1
fi

$psql -c "DROP DATABASE IF EXISTS $DATABASE" postgres
$psql -c "DROP USER IF EXISTS $DBOWNER" postgres
$psql -c "DROP USER IF EXISTS $DBUSER" postgres
$psql -c "CREATE DATABASE $DATABASE" postgres
$psql -c "CREATE USER $DBOWNER WITH PASSWORD '$DBOWNERPASSWORD';" postgres
$psql -c "CREATE USER $DBUSER WITH PASSWORD '$DBPASSWORD';" postgres
$psql -c "ALTER ROLE $DBOWNER SET client_encoding TO 'utf8'; ALTER ROLE $DBOWNER SET timezone TO 'UTC';" postgres
$psql -c "ALTER DATABASE $DATABASE OWNER TO $DBOWNER;" postgres
$psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $DBUSER" $DATABASE
$psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, UPDATE ON SEQUENCES TO $DBUSER" $DATABASE
#python3 manage.py migrate
#sudo -u vagrant bash -c "/var/www/coffeeshopsite/create_users.sh"
#sudo -u vagrant bash -c "/var/www/coffeeshopsite/loaddata.sh"
#sudo -u vagrant bash -c "/var/www/coffeeshopsite/collectstatic.sh"
