import os
import pymysql
pymysql.install_as_MySQLdb()

ENV_TYPE = os.getenv('RUNNING_ENV', 'base')

try:
    exec('from .{} import *'.format(ENV_TYPE))
except ImportError:
    from .base import *
