"""Tool to create syntetic benchmarks for DAWNets
"""

from __future__ import print_function
import pkgutil
import sys
import os
import logging
from io import open
from os import urandom
from base64 import b32encode
import dawnet.parser.dawnyaml as dawnyaml
from dawnet.parser.dawnet import embed_trace, DAWNet
from textx.metamodel import metamodel_from_str
from textx.exceptions import TextXError


PATTERN_GRAMMAR = pkgutil.get_data(__package__, 'bench_pattern.tx').decode()
PATTERN_MM = metamodel_from_str(PATTERN_GRAMMAR)


def new_uid(prefix='n', size=2):
    return '{}{}'.format(prefix, b32encode(urandom(size)).rstrip(b'='))


def benchmark_write(benchmark, outdir='.', embed=False):

    def writeTo(yaml_obj, name, tid, ftype):
        fname = '{}{}{}.yaml'.format(
            name,
            ('-' + tid if len(tid) > 0 else ''),
            ('-' + ftype if len(ftype) > 0 else '')
        )
        try:
            with open(os.path.join(outdir, fname), mode='w', encoding='utf-8') as fp:
                dawnyaml.write_obj(yaml_obj, fp)
        except IOError as e:
            logging.fatal('Failed to write to {}: {}'.format(fname, e))

    tname = dawnyaml.trace_name(benchmark.trace)

    if not embed:
        writeTo(benchmark.dawnet, benchmark.name, tname, '')

    for tid in benchmark.traceIDs():
        if embed:
            embedded_model = embed_trace(DAWNet(benchmark.dawnet), benchmark.filter_trace(tid))
            writeTo(dawnyaml.dawnet_yaml(embedded_model.name(), embedded_model.transitions()),
                    benchmark.name, (tname + '_' if tname else '') + tid, 'embedded_trace')
        else:
            writeTo(benchmark.filter_trace(tid), benchmark.name, (tname + '_' if tname else '') + tid, 'trace')


class BenchmarkCompiler:
    """Generates a benchmark from a given pattern"""
    logger = logging.getLogger('BenchmarkCompiler')
    pattern_mm = metamodel_from_str(PATTERN_GRAMMAR)

    @staticmethod
    def flatten_args(arglist):
        flat_args = []
        for subarg in arglist:
            if hasattr(subarg, '__iter__'):
                flat_args.extend(subarg)
            else:
                flat_args.append(subarg)
        return flat_args

    @classmethod
    def parse_pattern(cls, pattern):
        try:
            return cls.pattern_mm.model_from_str(pattern)
        except TextXError as e:
            logging.error("Error in benchmark pattern: {}".format(e))
            raise SystemExit

    @classmethod
    def generate(cls, pattern, base_benchmarks):
        bench_dict = {dawnyaml.model_name(bench.dawnet): bench for bench in base_benchmarks}

        def handle_spec(model):
            bench = apply_handler(model.bench)
            bench.dawnet[dawnyaml.DAWNET_NAME_KEY] = model.name
            bench.trace[dawnyaml.TRACE_MODEL_KEY] = model.name
            bench.name = model.name
            return bench

        def handle_mult(model):
            copies = model.num if model.num > 1 else 2
            bench = apply_handler(model.bench)
            new_benchs = [bench.duplicate(new_uid()) for i in range(0, copies)]
            return new_benchs

        def handle_netid(model):
            if model.name in bench_dict:
                return bench_dict[model.name].duplicate(new_uid(model.name + '_'))
            else:
                cls.logger.error('Missing base model for {}'.format(model.name))
                raise SystemExit

        def handle_seq(model):
            benchs = cls.flatten_args([apply_handler(bench) for bench in model.benchs])
            nid = new_uid('seq_')
            return Benchmark(
                dawnyaml.dawnet_sequential([b.dawnet for b in benchs], nid),
                dawnyaml.trace_sequential([b.trace for b in benchs], nid)
            )

        def handle_alt(model):
            benchs = cls.flatten_args([apply_handler(bench) for bench in model.benchs])
            nid = new_uid('alt_')
            return Benchmark(
                dawnyaml.dawnet_alternative([b.dawnet for b in benchs], nid),
                dawnyaml.trace_alternative([b.trace for b in benchs], nid)
            )

        def handle_par(model):
            benchs = cls.flatten_args([apply_handler(bench) for bench in model.benchs])
            nid = new_uid('par_')
            return Benchmark(
                dawnyaml.dawnet_parallel([b.dawnet for b in benchs], nid),
                dawnyaml.trace_parallel([b.trace for b in benchs], nid)
            )

        handlers = {
            'Spec': handle_spec,
            'Mult': handle_mult,
            'Seq': handle_seq,
            'Alt': handle_alt,
            'Par': handle_par,
            'NetID': handle_netid
        }

        def apply_handler(model):
            if type(model).__name__ in handlers:
                return handlers[type(model).__name__](model)
            else:
                cls.logger.error('Missing handler for {} object'.format(type(model).__name__))

        return apply_handler(cls.parse_pattern(pattern))

    @classmethod
    def test(cls, pattern):

        def spec_h(model):
            return '{}({})'.format(model.name, apply_handler(model.bench))

        def mult_h(model):
            subpattern = apply_handler(model.bench)
            return [subpattern for i in range(0, model.num)]

        def netid_h(model):
            return model.name

        def combine(op, benchs):
            return op + '(' + ', '.join(cls.flatten_args([apply_handler(bench) for bench in benchs])) + ')'

        def seq_h(model):
            return combine('SEQ', model.benchs)

        def alt_h(model):
            return combine('XOR', model.benchs)

        def par_h(model):
            return combine('AND', model.benchs)

        handlers = {
            'Spec': spec_h,
            'Mult': mult_h,
            'Seq': seq_h,
            'Alt': alt_h,
            'Par': par_h,
            'NetID': netid_h
        }

        def apply_handler(model):
            if type(model).__name__ in handlers:
                return handlers[type(model).__name__](model)
            else:
                cls.logger.error('Missing handler for {} object'.format(type(model).__name__))

        return apply_handler(cls.parse_pattern(pattern))


class Benchmark:
    ONLYIN_KEY = 'onlyin'

    def __init__(self, dawnet, trace=None, name=None):
        self.dawnet = dawnet
        self.trace = dawnyaml.trace_yaml(dawnyaml.model_name(self.dawnet)) if trace is None else trace
        self.name = dawnyaml.model_name(self.dawnet) if name is None else name

    @classmethod
    def from_files(self, dawnet_file, trace_file=None):
        if hasattr(dawnet_file, 'read'):
            dawnet = dawnyaml.readDAWNETobj(dawnet_file)
        else:
            with open(dawnet_file, encoding='utf-8') as fd:
                dawnet = dawnyaml.readDAWNETobj(fd)
        if trace_file and hasattr(trace_file, 'read'):
            trace = dawnyaml.readTraceObj(trace_file)
        elif trace_file:
            with open(trace_file, encoding='utf-8') as fd:
                trace = dawnyaml.readTraceObj(fd)
        else:
            trace = None

        return Benchmark(dawnet, trace)

    def duplicate(self, new_name):
        return Benchmark(
            dawnyaml.copy_model(self.dawnet, new_name),
            dawnyaml.copy_trace(self.trace, new_name)
        )

    def to_files(self, outdir):
        model_fname = '{}.yaml'.format(self.name)
        try:
            with open(os.path.join(outdir, model_fname), 'w') as fp:
                dawnyaml.write_obj(self.dawnet, fp)
        except IOError as e:
            logging.fatal('Failed to write model to {}: {}'.format(model_fname, e))
        for tid in self.traceIDs():
            trace_fname = '{}{}-trace.yaml'.format(self.name, '_' + tid if len(tid) > 0 else '')
            try:
                with open(os.path.join(outdir, trace_fname), 'w') as fp:
                    dawnyaml.write_obj(self.filter_trace(tid), fp)
            except IOError as e:
                logging.fatal('Failed to write trace{} to {}: {}'.format(' ' + tid if len(tid) > 0 else '', trace_fname, e))

    def dump(self, fp=sys.stdout):
        dawnyaml.write_obj({
            'name': self.name,
            'dawnet': self.dawnet,
            'traces': {tid: self.filter_trace(tid) for tid in self.traceIDs()}
        }, fp)

    def traceIDs(self):
        tids = set(['all'])
        for transition in dawnyaml.trace_transitions(self.trace):
            tids.update(transition.get(self.ONLYIN_KEY, []))
        return tids

    def filter_trace(self, tid):
        if len(tid) > 0 and tid != 'all':
            filtered_transitions = [
                transition for transition in dawnyaml.trace_transitions(self.trace) if tid in transition.get(self.ONLYIN_KEY, [])
            ]
            trace_name = dawnyaml.trace_name(self.trace)
            return dawnyaml.trace_yaml(
                dawnyaml.trace_model(self.trace), filtered_transitions,
                name=(trace_name + '_' if trace_name else '') + tid)
        else:
            return self.trace

    @property
    def dawnet(self):
        return self._dawnet

    @dawnet.setter
    def dawnet(self, value):
        self._dawnet = value

    @property
    def trace(self):
        return self._trace

    @trace.setter
    def trace(self, value):
        self._trace = value

    @property
    def name(self):
        return self._bench_name

    @name.setter
    def name(self, value):
        self._bench_name = str(value)


def read_string(source):
    try:
        source_str = source.read()
    except AttributeError:
        try:
            with open(source, encoding='utf-8') as fd:
                source_str = fd.read()
        except IOError:
            source_str = str(source)
    return source_str


def generate_benchmark(pattern, base_models):
    return BenchmarkCompiler.generate(read_string(pattern), base_models)


def test_pattern(pattern):
    return BenchmarkCompiler.test(read_string(pattern))


def benchmark_from_files(files):
    """Assume a list of pairs dawnet trace, returns a list of benchmarks
    """
    if len(files) == 0 or (len(files) > 1 and len(files) % 2 == 1):
        logging.error("Benchmark creation requires an even number of files.")
        raise SystemExit
    if len(files) > 1:
        return [
            Benchmark.from_files(files[i], files[i + 1]) for i in range(0, len(files), 2)
        ]
    else:
        return [Benchmark.from_files(files[0])]


def main(pattern, *files):
    logging.basicConfig()
    if len(files) > 0:
        base_models = benchmark_from_files(files)
        generate_benchmark(pattern, base_models).dump()
    else:
        print(test_pattern(pattern))


if __name__ == '__main__':
    main(*sys.argv[1:])
