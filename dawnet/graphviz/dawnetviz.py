#!/usr/bin/env python

"""\
Export a DAWNet file to a Graphviz dot file
"""
from __future__ import print_function

import os
import sys
import shutil
from dawnet import utils
from dawnet.parser import dawnet
from jinja2 import Environment, FileSystemLoader
import logging


def guard2string(gobj):
    if isinstance(gobj, dict):
        op = gobj['op']
        args = gobj['args']
        if op == 'AND':
            return "({})".format(' & '.join([guard2string(i) for i in args]))
        elif op == 'OR':
            return "({})".format(' | '.join([guard2string(i) for i in args]))
        else:
            return "{}{}{}".format(args[0], op, args[1])
    else:
        return gobj


ENV = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
    trim_blocks=True,
    lstrip_blocks=True)

ENV.globals['guard2string'] = guard2string


def get_configuration(option, default=None):
    section = 'graphviz'
    default_values = {
        'command': 'dot -Tsvg'
    }

    optvalue = utils.get_conf(section, option, default, default_values)

    if option == 'command':
        return utils.conf_shell_list(optvalue)
    else:
        return optvalue


def render_dawnets_dot(dawnet, file=None):
    template = ENV.get_template('dawnetviz_template.dot')
    ctx = {
        'name': dawnet.name(),
        'transitions': dawnet.transitions(),
        'places': dawnet.placeNames(),
        'dawnet': dawnet
    }
    if file:
        template.stream(ctx).dump(file)
    else:
        return template.render(ctx)


def run_dot(source_path, workdir, outfile):
    command = get_configuration('command')
    command.append(source_path)

    utils.run_solver(command, stdout=outfile, timeit=False)


def process_model(dawnet, outfile=sys.stdout, solve=False, keep=False, tempdir=None):
    if solve:
        tdir = utils.tempdir(prefix='dawnets_dot_', dir=tempdir)
        logging.info("Temporary dir in {}".format(tdir))
        dotpath = os.path.join(tdir, '{}.dot'.format(dawnet.name()))
        with open(dotpath, 'w') as dotfile:
            render_dawnets_dot(dawnet, dotfile)
        run_dot(dotpath, tdir, outfile)
        if not keep:
            shutil.rmtree(tdir)
    else:
        render_dawnets_dot(dawnet, outfile)


def main(stream):
    print(render_dawnets_dot(dawnet.readDAWNET(stream)))


if __name__ == '__main__':
    main(file(sys.argv[1], 'r'))