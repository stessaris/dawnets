"""Run DAWNet benchmarks described in YAML/JSON files
"""

import logging
import datetime
import os
from os import urandom
from base64 import b32encode
import errno
import subprocess
import json
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
import sys
try:
    # >3.2
    from configparser import ConfigParser
except ImportError:
    # python27
    # Refer to the older SafeConfigParser as ConfigParser
    from ConfigParser import SafeConfigParser as ConfigParser

DRYRUN = os.environ.get('DRYRUN')

OUTDIR = os.path.join("benchmarks_results", "{datetime}")
DAWNETS_CMD = 'dawnets'
RUN_OUTDIR = os.path.join('{name}')
OUTFILE = os.path.join(RUN_OUTDIR, '{cmd}_out.txt')
ERRFILE = os.path.join(RUN_OUTDIR, '{cmd}_err.txt')
STATSFILE = os.path.join(RUN_OUTDIR, '{cmd}_stats.json')
LOGFILE = os.path.join(RUN_OUTDIR, 'logfile.txt')
TMPDIR = RUN_OUTDIR
TIMEOUT = 3600
MEMORY = 0          # no memory limits
DEFAULT_RUNS = {
    'coala': {'args': ['-z', 20]},
    'pddl': {'args': []},
    'nusmv': {'args': []}
}
TIMESTAMP_FMT = r'%Y%m%dT%H%M%SZ'

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


def ensure_path(path, writable=True):
    logging.debug('Checking path {}'.format(path))
    if not DRYRUN:
        # make sure the output directory exists
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        else:
            logging.info('Creating directory {}'.format(path))
        # verify that's writable
        if writable and not os.access(path, os.W_OK):
            raise OSError(errno.EACCES, 'Directory is not writable', path)
    return path


def writable_file(path):
    ensure_path(os.path.dirname(path))
    return path


def merge_config(global_cfg, local_cfg):
    if global_cfg is None:
        return local_cfg
    else:
        for (section, options) in global_cfg.items():
            if section not in local_cfg:
                local_cfg[section] = {}
            for (option, value) in options.items():
                if option not in local_cfg[section]:
                    local_cfg[section][option] = value
        return local_cfg


def writeConfig(config_obj, file_path, macros={}):
    """Writes the configuration into a file.
    """
    config = ConfigParser()
    for (section, options) in config_obj.items():
        config.add_section(section)
        for (option, value) in options.items():
            config.set(section, option, str(value).format(**macros))

    try:
        with open(file_path, 'w') as fp:
            config.write(fp)
    except IOError:
        logging.critical("Cannot write on {}".format(file_path))


def new_bid(prefix='benchmark_', size=2):
    return '{}{}'.format(prefix, b32encode(urandom(size)).rstrip(b'='))


def run_benchmark(name, inputs, outdir, cmd,
                  basedir='',
                  bid=None,
                  config=None,
                  keep=True,
                  timeout=TIMEOUT,
                  memlimit=MEMORY,
                  cmd_args=[],
                  docker=None,
                  dawnets_exec=DAWNETS_CMD,
                  stdout_file=OUTFILE,
                  stderr_file=ERRFILE,
                  stats_file=STATSFILE,
                  tmpdir=TMPDIR,
                  models_path='',
                  workdir=None,
                  logfile=LOGFILE,
                  timestamp=None):

    if bid is None:
        bid = new_bid()
    if timestamp is None:
        timestamp = datetime.datetime.utcnow().strftime(TIMESTAMP_FMT)

    expand_macros = {
        'id': bid,
        'cmd': cmd,
        'datetime': timestamp,
        'home': os.path.join(os.path.expanduser("~"), ""),
        'name': name,
    }

    def expnd(value):
        return value.format(**expand_macros)

    def xpand_path(path, prefix=None):
        return os.path.abspath(
            os.path.join(prefix if prefix is not None else basedir, os.path.expanduser(expnd(path))))

    outdir = ensure_path(xpand_path(outdir))
    expand_macros['outdir'] = os.path.join(outdir, '')

    workdir = ensure_path(xpand_path(workdir if workdir is not None else ''))
    expand_macros['wd'] = os.path.join(workdir, '')

    expand_macros['models'] = os.path.join(xpand_path(models_path), '')

    stats_path = writable_file(xpand_path(stats_file, prefix=outdir))
    if logfile is not None:
        log_path = writable_file(xpand_path(logfile, prefix=outdir))
    tmpdir_path = ensure_path(xpand_path(tmpdir, prefix=outdir))

    dawnet_command = [dawnets_exec] if isinstance(dawnets_exec, str if sys.version_info[0] >= 3 else basestring) else list(dawnets_exec)
    dawnet_command.extend([
        '--solve',
        '--stdout', writable_file(os.path.join(outdir, expnd(stdout_file))),
        '--stderr', writable_file(os.path.join(outdir, expnd(stderr_file))),
        '--stats', stats_path,
        '--tmpdir', tmpdir_path
    ])
    if config:
        cfg_file = writable_file(os.path.join(tmpdir_path, '{}_{}.ini'.format(name, cmd)))
        if not DRYRUN:
            writeConfig(config, cfg_file, macros=expand_macros)
        dawnet_command.extend(['--config', cfg_file])
    if keep:
        dawnet_command.append('--keep')
    if timeout > 0:
        dawnet_command.extend(['--timeout', str(timeout)])
    if memlimit > 0:
        dawnet_command.extend(['--memlimit', str(memlimit)])
    if logfile is not None:
        dawnet_command.extend(['--logfile', log_path])

    dawnet_command.append(cmd)
    dawnet_command.extend([expnd(a) for a in cmd_args])
    dawnet_command.extend([xpand_path(f) for f in inputs])

    bench_command = docker + dawnet_command if docker else dawnet_command

    logging.info('Executing `{}`'.format(' '.join(bench_command)))
    try:
        if not DRYRUN:
            starttime = datetime.datetime.utcnow().strftime(TIMESTAMP_FMT)
            subprocess.call(bench_command, cwd=workdir)

            # Update the statistics file with run details
            try:
                with open(stats_path, 'r') as fp:
                    stats_obj = json.load(fp)
            except IOError:
                stats_obj = {}
            stats_obj['name'] = name
            stats_obj['inputs'] = [expnd(f) for f in inputs]
            stats_obj['timestamp'] = timestamp
            stats_obj['solver'] = cmd
            stats_obj['dawnet_exec'] = dawnet_command
            stats_obj['start_time'] = starttime
            stats_obj['id'] = bid
            try:
                with open(stats_path, 'w') as fp:
                    json.dump(stats_obj, fp, indent=2, sort_keys=True)
            except IOError as e:
                logging.critical('Failed to write {}'.format(stats_path))

    except OSError as e:
        logging.error('Error {} running {}'.format(e.strerror, ' '.join(bench_command)))


def run_benchmark_set(description, basedir=None):

    timestamp = datetime.datetime.utcnow().strftime(TIMESTAMP_FMT)

    try:
        bid = description.get('id', new_bid())
        benchmarks = description['benchmarks']
        outdir = description.get('outdir', OUTDIR)
        docker_cmd = description.get('docker', [])
        timeout = description.get('timeout', TIMEOUT)
        memlimit = description.get('memory', MEMORY)
        global_config = description.get('config')
        dawnets_exec = description.get('exec', DAWNETS_CMD)
        stdout_file = description.get('stdout', OUTFILE)
        stderr_file = description.get('stderr', ERRFILE)
        stats_file = description.get('stats', STATSFILE)
        log_file = description.get('logfile', LOGFILE)
        default_runs = description.get('runs', DEFAULT_RUNS)
        tmpdir = description.get('tmpdir', TMPDIR)
        models_path = description.get('models_path', '')
        workdir = description.get('workdir')

    except KeyError as e:
        logging.critical('Missing global key {}'.format(e))
    else:
        try:
            for (name, benchmrk) in benchmarks.items():
                if 'config' in benchmrk:
                    local_config = merge_config(global_config, benchmrk['config'])
                else:
                    local_config = global_config
                infiles = benchmrk['files']
                for (cmd, run) in benchmrk.get('runs', default_runs).items():
                    cmd_args = run.get('args', [])
                    run_benchmark(name, infiles, outdir, cmd,
                                  basedir=basedir if basedir is not None else os.getcwd(),
                                  bid=bid,
                                  config=local_config,
                                  keep=True,
                                  timeout=timeout,
                                  memlimit=memlimit,
                                  cmd_args=cmd_args,
                                  docker=docker_cmd,
                                  dawnets_exec=dawnets_exec,
                                  stdout_file=stdout_file,
                                  stderr_file=stderr_file,
                                  stats_file=stats_file,
                                  tmpdir=tmpdir,
                                  models_path=models_path,
                                  workdir=workdir,
                                  logfile=log_file,
                                  timestamp=timestamp)
        except KeyError as e:
            logging.error('Missing benchmark key {}'.format(e))


def read_benchmark(stream):
    try:
        description = YAML().load(stream)
    except YAMLError as e:
        logging.critical("Benchmark description is not an YAML/JSON file: {}".format(e.message))
        return None
    else:
        return description


def read_and_run(path_or_file, basedir=None):
    if hasattr(path_or_file, 'read'):
        description = read_benchmark(path_or_file)
        if basedir is None and hasattr(path_or_file, 'name'):
            basedir = os.path.dirname(os.path.realpath(path_or_file.name))
    else:
        with open(path_or_file, 'r') as fp:
            description = read_benchmark(fp)
        if basedir is None:
            basedir = os.path.dirname(os.path.realpath(path_or_file))
    if description is not None:
        run_benchmark_set(description, basedir=basedir)


def benchmarks_from_files(source, basedir=None):
    if os.path.isdir(source):
        for root, dirs, files in os.walk(source):
            for name in files:
                read_and_run(os.path.join(root, name), basedir=basedir)
    elif os.path.exists(source):
        read_and_run(source, basedir=basedir)


def main(args):
    if len(args) > 1:
        for bpath in args[1:]:
            benchmarks_from_files(bpath)
    else:
        read_and_run(sys.stdin)


if __name__ == '__main__':
    main(sys.argv)
