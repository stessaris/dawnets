from __future__ import print_function
import logging
import shlex
import os
import sys
import json
from builtins import int  # PYthon 2/3 compatibility <http://python-future.org/compatible_idioms.html#long-integers>
from dawnet import CONFIG, __version__
import tempfile
from runner import Runner

MAIN_CONF_SECTION = 'Main'


def set_mem_limit(size_b):
    logging.info('Setting memory limit to {}'.format(size_b))
    Runner.set_memlimit(size_b)


def get_config():
    """Returns the object holding the configuration"""
    return CONFIG


def config_json():
    conf_json = {}
    for section in get_config().sections():
        conf_json[section] = {}
        for (name, value) in get_config().items(section):
            conf_json[section][name] = value
    return conf_json


def get_main_conf(option, default=None, type=None):
    return get_conf(MAIN_CONF_SECTION, option, value=default, type=type)


def set_main_conf(option, value):
    set_conf(MAIN_CONF_SECTION, option, value)


def get_conf(section, option, value=None, defaults=None, type=None):
    if defaults:
        if option not in defaults:
            logging.warning('Undefined option {}.{}'.format(section, option))
        elif value is None:
            value = defaults[option]
    conf_value = get_config().get(section, option) if get_config().has_option(section, option) else value
    if type == 'bool' or type == bool:
        return conf_boolean(conf_value)
    elif type == 'int' or type == int:
        return conf_integer(conf_value)
    else:
        return conf_value


def set_conf(section, option, value):
    if value is not None:
        if not get_config().has_section(section):
            get_config().add_section(section)
        get_config().set(section, option, str(value))


def conf_shell_list(value):
    return shlex.split(value) if value is not None else None


def conf_boolean(value):
    if value is None:
        return None
    _boolean_states = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}
    if value.lower() not in _boolean_states:
        logging.error('Option value not a boolean: {}'.format(value))
    return _boolean_states[value.lower()]


def conf_integer(value):
    try:
        return int(value) if value is not None else None
    except ValueError:
        logging.error('Option value not an integer: {}'.format(value))
        return 0


def run_solver(command, stdout=sys.stdout, stderr=sys.stderr,
               timeout=None, memlimit=None,
               timeit=True, stats_out=None):
    if timeout is None:
        timeout = conf_integer(get_main_conf('timeout'))
    if stats_out is None:
        stats_out = get_main_conf('stats_file')
    if memlimit is None:
        memlimit = conf_integer(get_main_conf('memlimit', default=0))
    tmout_val = timeout if isinstance(timeout, int) and timeout > 0 else None
    logging.info('Running "{}"{}'.format(' '.join(command), " with timeout " + str(tmout_val) if tmout_val else ''))

    stats = {}
    try:
        stats = Runner.run_with_timeout(command, timeout=timeout, memlimit=memlimit)

        if stats.get('exit_status', 0) != 0 or stats.get('timeout_happened', False):
            logging.warning('Process {}{}{}'.format(
                command[0],
                ' timed out' if stats.get('timeout_happened', False) else ' terminated',
                ' with exit code {}'.format(stats.get('exit_status', None))))

        if stats.get('stderr', None) is not None:
            for el in stats['stderr'].splitlines():
                logging.error(' {} errors: {}'.format(command[0], el))
        else:
            logging.warning('Missing stderr for {}'.format(command[0]))

        if stats.get('stdout', None) is not None:
            stdout.write(stats['stdout'])

        if stats.get('timeout_happened', False):
            print('Process {} timed out after {} seconds'.format(command[0], timeout), file=stdout)

    except OSError as e:
        logging.error("Error running '{}': {}".format(command[0], e))
        stats['stderr'] = "Error running '{}': {}".format(command[0], e)

    if timeit:
        # rename command key
        if 'command' in stats:
            stats['solver_exec'] = stats.pop('command')
        stats['version'] = __version__
        stats['config'] = config_json()

        if stats_out:
            with open(stats_out, 'w') as fp:
                json.dump(stats, fp, sort_keys=True, indent=2)
        else:
            print('Resources used by `{}`'.format(' '.join(command)), file=stdout)
            if stats.get('rtime', None) is not None:
                print('{:25} ({:10}) = {}'.format('Real time', 'N/A', stats.get('rtime', 'N/A')), file=stdout)
            for name, desc in Runner.RUSAGE_KEYS.items():
                print('{:25} ({:10}) = {}'.format(desc, name, stats.get(name, 'N/A')), file=stdout)


def tempdir(suffix="", prefix="tmp", dir=None, mode=0o755):
    """Create a temporary folder and set the permissions."""
    try:
        path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        os.chmod(path, mode)
        return path
    except Exception as e:
        raise e


def add_logging_handler(name=None, level=logging.INFO, stream=sys.stderr, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'):
    logger = logging.getLogger() if name is None else logging.getLogger(str(name))

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    formatter = logging.Formatter(fmt=format, datefmt=datefmt)
    handler.setFormatter(formatter)

    logger.addHandler(handler)
