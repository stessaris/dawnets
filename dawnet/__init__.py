# Initialises package variables

import pkgutil
import logging
from io import StringIO
import os
import subprocess
try:
    # >3.2
    from configparser import ConfigParser
except ImportError:
    # python27
    # Refer to the older SafeConfigParser as ConfigParser
    from ConfigParser import SafeConfigParser as ConfigParser

# DAWNets tool version number
__version__ = "1.0"


def get_version(git=True):
    _git_revision_ = None
    if git:
        try:
            _git_revision_ = subprocess.check_output(['git', 'describe', '--always', '--dirty'], stderr=open(os.devnull, 'w')).decode("utf-8").strip()
        except subprocess.CalledProcessError:
            pass
    return __version__ + ('' if _git_revision_ is None else '+' + _git_revision_)


# Read a configuration file
#   looks within the package (defaults) and in the current directory
#
CONFIG_FILE = 'dawnets.ini'
CONFIG = ConfigParser()

try:
    defaults = pkgutil.get_data(__name__, CONFIG_FILE).decode()
    CONFIG.readfp(StringIO(defaults))
except Exception as e:
    logging.warning("Missing package configuration file: {}".format(e.message))

CONFIG.read(CONFIG_FILE)
