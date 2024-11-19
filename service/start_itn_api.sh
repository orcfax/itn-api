#! /usr/bin/bash

source /home/orcfax/itn-api/api.env

/home/orcfax/itn-api/venv/bin/python /home/orcfax/itn-api/itn_api.py --workers 5
