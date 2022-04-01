#!/bin/sh
python3 /usr/src/app/manage.py dumpdata --exclude auth.permission --exclude contenttypes > /usr/src/app/backups/backup$(date +%s).txt