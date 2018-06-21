#!/bin/bash

#===================================================================================================
#   Project:            Mind cloud
#   Author:             Buldey Alexander
#   Contact:            https://t.me/Alex_Booldey
#   Description:        The script drop the tables articles, history, categories
#   Version:           	1.0
#   History:          	May 23, 2018 - Created
#===================================================================================================

user_name=$1
user_pass=$2
db_name=$3 

if  [ -n "$1" ] | [ -n "$2" ] | [ -n "$3" ] 
then
mysql --user=${user_name} --password=${user_pass} ${db_name} < drop_table_categories.sql
mysql --user=${user_name} --password=${user_pass} ${db_name} < drop_table_history.sql
else
echo "ERROR parameters!"
echo "Exsample >drop_wiki_tables.sh [user_name] [user pass] [db_name]"
fi

