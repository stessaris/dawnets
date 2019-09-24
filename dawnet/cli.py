"""Parse and transform DAWNETS YAML/JSON files.

"""

from __future__ import print_function
import sys
import codecs
import click
import logging
import os
import errno

from . import utils
from . import get_version
from dawnet.parser.dawnet import readDAWNET, readTrace, embed_trace
import dawnet.graphviz.dawnetviz as dawnetviz
import dawnet.coala.dawnetcoala as dawnetcoala
import dawnet.pddl.dawnetpddl as dawnetpddl
import dawnet.nusmv.dawnetnusmv as dawnetnusmv
from dawnet.benchmarks import syntetic, run_benchmark

# fix the encoding problems when pipinig stdout
#   see e.g. <http://www.macfreek.nl/memory/Encoding_of_Python_stdout#StreamWriter_Wrapper_around_Stdout>
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout, 'strict')
if sys.stderr.encoding != 'UTF-8':
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr, 'strict')


def getTraceModel(model, trace):
    """Read a DAWNet from the model stream and if trace is not None incorporates it into the model
    """
    if trace:
        return embed_trace(readDAWNET(model), readTrace(trace))
    else:
        return readDAWNET(model)


def cli_opt(ctx, option, default=None):
    if option in ctx.obj:
        return ctx.obj[option]
    else:
        logging.error("Missing global option {}".format(option))
        return default


def cli_set_opt(ctx, option, value):
    if utils.get_main_conf(option) is None or value:
        utils.set_main_conf(option, value)
        ctx.obj[option] = value
    else:
        ctx.obj[option] = utils.get_main_conf(option)


@click.group()
@click.version_option(version=get_version())
@click.option('--config', '-c', type=click.File('r'), help='Configuration file')
@click.option('--solve', '-s', is_flag=True, envvar='SOLVE', help='Solve the problem using the appropriate tool')
@click.option('--keep', '-k', is_flag=True, envvar='KEEP', help='Keep intermediate files')
@click.option('-v', '--verbose', count=True, help='Increase logging verbosity')
@click.option('--stdout', type=click.File('a'), help='Redirect standard output to file')
@click.option('--stderr', type=click.File('a'), help='Redirect standard error to file')
@click.option('--tmpdir', type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True, resolve_path=True),
              help='Directory for temporary files')
@click.option('--timeout', type=click.INT, help='Stop the solver after the number of seconds')
@click.option('--memlimit', type=click.INT, help='Limit the amount of memory for the solver (in bytes)')
@click.option('--stats', type=click.Path(file_okay=True, dir_okay=False, writable=True), help='Solver stats are written in this file')
@click.option('--logfile', type=click.File('a'), help='Logs are written in this file')
@click.option('--usejson', is_flag=True, envvar='JSONFORMAT', help='Use JSON parser to read input files')
@click.option('--reducedomain', is_flag=True, help='Reduce the active domain to consider only the constants used in the guards')
@click.option('--nodata', is_flag=True, help="Don't include the data part in the encoding.")
@click.pass_context
def cli(ctx, config, solve, keep, verbose, stdout, stderr, tmpdir, timeout, memlimit, stats, logfile, usejson, reducedomain, nodata):
    """Encode DAWNet reachability problems.
    To see the commands usage run 'command' --help
    """
    if config:
        utils.get_config().readfp(config)

    # Setup stdout/stderr streams and logging
    if stdout:
        sys.stdout = stdout
    if stderr:
        sys.stderr = stderr

    if verbose > 1:
        logLevel = logging.DEBUG
    elif verbose > 0:
        logLevel = logging.INFO
    else:
        logLevel = logging.WARNING

    # get rid of default logging handlers
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    # Add stderr logging handler
    utils.add_logging_handler(level=logLevel, stream=sys.stderr)
    # Logfile
    cli_set_opt(ctx, 'logfile', logfile)
    if logfile is not None:
        utils.add_logging_handler(level=logLevel, stream=logfile)

    cli_set_opt(ctx, 'solve', solve)
    cli_set_opt(ctx, 'keep', keep)
    cli_set_opt(ctx, 'tmpdir', tmpdir)
    cli_set_opt(ctx, 'timeout', timeout)
    cli_set_opt(ctx, 'memlimit', memlimit)
    if memlimit:
        utils.set_mem_limit(memlimit)
    cli_set_opt(ctx, 'stats_file', stats)
    cli_set_opt(ctx, 'usejson', usejson)
    cli_set_opt(ctx, 'reducedomain', reducedomain)
    cli_set_opt(ctx, 'nodata', nodata)


@cli.command()
@click.pass_context
def config(ctx):
    """Shows the configuration options
    """
    utils.get_config().write(sys.stdout)


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.pass_context
def show(ctx, model, trace):
    """Print a description of the model.
    If the trace is given then it's incorporated into the model.
    """
    dawnet = getTraceModel(model, trace)
    dawnet.show()


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'))
@click.option('--outfile', '-o', type=click.File('w'), help='output file')
@click.pass_context
def trace(ctx, model, trace, outfile):
    """Output a model augmented with the given trace.
    """
    dawnet = getTraceModel(model, trace)
    dawnet.toYAML(outfile if outfile else sys.stdout)


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.pass_context
def validate(ctx, model, trace):
    """Read the model to check whether it's well formed.
    If the trace is given then it's incorporated into the model.
    """
    getTraceModel(model, trace)


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.option('--outfile', '-o', type=click.File('w', encoding='utf-8'), help='output file')
@click.pass_context
def dot(ctx, model, trace, outfile):
    """Generates a Graphviz representation of the model.
    If the trace is given then it's incorporated into the model.
    """
    dawnet = getTraceModel(model, trace)
    dawnetviz.process_model(dawnet, outfile=outfile if outfile else sys.stdout,
                            solve=cli_opt(ctx, 'solve'), keep=cli_opt(ctx, 'keep'),
                            tempdir=cli_opt(ctx, 'tmpdir'))


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.option('--outfile', '-o', type=click.File('w'), help='output file')
@click.option('--data/--no-data', default=True, help='include data part of the encoding [default=ON]')
@click.option('--horizon', '-z', default=20, type=click.INT, help='Maximun plan lenght for the solver')
@click.pass_context
def coala(ctx, model, trace, outfile, data, horizon):
    """Generates a Coala encoding of the model.
    If the trace is given then it's incorporated into the model.
    """
    dawnet = getTraceModel(model, trace)
    dawnetcoala.process_model(dawnet,
                              outfile=outfile if outfile else sys.stdout,
                              solve=cli_opt(ctx, 'solve'),
                              horizon=horizon,
                              keep=cli_opt(ctx, 'keep'),
                              nodata=(not data),
                              tempdir=cli_opt(ctx, 'tmpdir'))


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.option('--outfile', '-o', type=click.File('w'), help='output file')
@click.option('--outdir', '-o', type=click.Path(exists=True, file_okay=False, writable=True),
              help='output directory for saving PDDL domain and problem files')
@click.pass_context
def pddl(ctx, model, trace, outfile, outdir):
    """Generates a PDDL encoding of the model.
    If the trace is given then it's incorporated into the model.
    If the output directory is given the domain and problem files are written.
    """
    dawnet = getTraceModel(model, trace)
    dawnetpddl.process_model(
        dawnet, outfile=outfile if outfile else sys.stdout,
        solve=cli_opt(ctx, 'solve'), keep=cli_opt(ctx, 'keep'),
        outdir=outdir if outdir else cli_opt(ctx, 'tmpdir')
    )


@cli.command()
@click.argument('model', type=click.File('r'))
@click.argument('trace', type=click.File('r'), required=False)
@click.option('--outfile', '-o', type=click.File('w'), help='output file')
@click.pass_context
def nusmv(ctx, model, trace, outfile):
    """Generates a nuSMV encoding of the model.
    If the trace is given then it's incorporated into the model.
    """
    dawnet = getTraceModel(model, trace)
    dawnetnusmv.process_model(dawnet, outfile=outfile if outfile else sys.stdout,
                              solve=cli_opt(ctx, 'solve'), keep=cli_opt(ctx, 'keep'),
                              tempdir=cli_opt(ctx, 'tmpdir'))


@cli.command()
@click.argument('pattern', type=click.STRING)
@click.argument('models', type=click.File('r'), nargs=-1)
@click.option('--outdir', '-o', type=click.Path(file_okay=False), help='output directory')
@click.option('--embed/--no-embed', default=False, help='embeds traces into the model [default=OFF]')
@click.pass_context
def benchmark(ctx, pattern, models, outdir, embed):
    """Generates a benchmark based on the given pattern using the models, pairs of DAWNet and traces.

    The pattern is based on the following grammar:\n
        Spec: ID Benchmark;\n
        Benchmark: Seq | Alt | Par | NetID;\n
        Benchmarks: Benchmark Benchmarks | Mult\n
        Mult: '[' INT ']' Benchmark;\n
        Seq: '(' ';' Benchmarks ')';\n
        Alt: '(' 'x' Benchmarks ')';\n
        Par: '(' '+' Benchmarks ')';\n
        NetID: ID;
    """
    if len(models) > 0:
        if outdir:
            try:
                os.makedirs(outdir, mode=0o777)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    logging.error('Cannot create directory {}'.format(outdir))
                    outdir = None
        base_benchmarks = syntetic.benchmark_from_files(models)
        benchmark = syntetic.generate_benchmark(pattern, base_benchmarks)
        if outdir:
            syntetic.benchmark_write(benchmark, outdir=outdir, embed=embed)
        else:
            benchmark.dump()
    else:
        print(syntetic.test_pattern(pattern))


@cli.command()
@click.argument('benchmarks', type=click.File('r'), nargs=-1)
def run(benchmarks):
    """Run the given benchmarks described as YAML files.
    """
    for fd in benchmarks:
        run_benchmark.read_and_run(fd)


@cli.command()
@click.argument('cmdargs', required=True, nargs=-1)
@click.pass_context
def runcmd(ctx, cmdargs):
    """Execute the given command"""
    utils.run_solver(cmdargs)


def main():
    cli(obj={})


if __name__ == '__main__':
    # sys.exit(main(sys.argv[1:]))
    main()
