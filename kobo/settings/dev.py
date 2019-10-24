# coding: utf-8
from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import sys

from .base import *

LOGGING['handlers']['console'] = {
    'level': 'DEBUG',
    'class': 'logging.StreamHandler',
    'formatter': 'verbose'
}

# When using `./manage.py runserver_plus`, print output is not
# displayed in the console and later when buffer is flushed.
# This monkey-patch makes stout.write to flush buffer right away
# sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

# Comment out the line below to use `Django Debug Toolbar`
# INTERNAL_IPS = ['172.24.0.3']  # Change IP to KPI container's IP
