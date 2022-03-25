#!/bin/sh
python3 /usr/src/app/manage.py dumpdata > /usr/src/app/backups/backup$(date +%s).txt