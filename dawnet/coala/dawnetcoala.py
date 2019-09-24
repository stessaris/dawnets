#!/usr/bin/env python

"""\
Transform a DAWNet file into a Coala planner problem
"""
from __future__ import print_function

import os
import sys
import logging
import shutil
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from dawnet.parser import dawnet
from dawnet import utils


def get_configuration(option, default=None):
    section = 'coala'
    default_values = {
        'command': 'coala -p -m s',
        'timeout': '0',
        'data': 'True'
    }

    optvalue = utils.get_conf(section, option, default, default_values)

    if option == 'command':
        return utils.conf_shell_list(optvalue)
    elif option == 'timeout':
        return utils.conf_integer(optvalue)
    elif option == 'data':
        return utils.conf_boolean(optvalue)
    else:
        return optvalue


def coalaConst(name):
    sanitised = str(name).replace(' ', '_').strip("'")
    # make sure that the first char is a lowercase letter
    if sanitised[0].isupper():
        sanitised = sanitised[0].lower() + sanitised[1:]
    elif not (sanitised[0].islower() or sanitised.isdigit()):
        # prepend lowercase letter
        sanitised = 'c' + sanitised
    return sanitised


def guard_to_rules(tr_name, guard_expr):

    rules = []
    guard_to_rules.lastLevel = -1

    def guard_fluent(level):
        return 'guard({})'.format(coalaConst(tr_name)) if level < 0 else 'guard({},{})'. format(coalaConst(tr_name), level)

    def store_rule(level, body):
        rules.append((guard_fluent(level), body))

    def next_level():
        guard_to_rules.lastLevel += 1
        return guard_to_rules.lastLevel

    def rule_term(guard):
        if guard.isOR():
            level = next_level()
            for or_term in guard.getArguments():
                store_rule(level, rule_body(or_term))
            return guard_fluent(level)
        elif guard.isAND():
            level = next_level()
            body = [rule_term(and_term) for and_term in guard.getArguments()]
            store_rule(level, body)
            return guard_fluent(level)
        elif guard.isComparison():
            return "{}{}{}".format(coalaConst(guard.lhs()), guard.getOperator(), coalaConst(guard.rhs()))
        else:
            return str(guard)

    def rule_body(guard):
        if guard.isOR():
            level = next_level()
            for or_term in guard.getArguments():
                store_rule(level, rule_body(or_term))
            return [guard_fluent(level)]
        elif guard.isAND():
            return [rule_term(and_term) for and_term in guard.getArguments()]
        elif guard.isComparison():
            return ["{}{}{}".format(coalaConst(guard.lhs()), guard.getOperator(), coalaConst(guard.rhs()))]
        else:
            return [str(guard)]

    if guard_expr.isOR():
        for or_term in guard_expr.getArguments():
            store_rule(guard_to_rules.lastLevel, rule_body(or_term))
    else:
        store_rule(guard_to_rules.lastLevel, rule_body(guard_expr))
    return rules


ENV = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')),
    trim_blocks=True,
    lstrip_blocks=True)


# Export the guard parsing function to Jinja2 templates
ENV.globals['coalaConst'] = coalaConst


def render_dawnets_coala(dawnet, nodata=False, encoding='easyEnc', stream=sys.stdout):
    try:
        templ_name = '{enc}_planning.bc'.format(enc=encoding)
        template = ENV.get_template(templ_name)
    except TemplateNotFound:
        logging.error('missing template {}'.format(templ_name))
        return ''
    return render_dawnets(dawnet, template, stream, nodata)


def render_dawnets(dawnet, template, stream, nodata=False):
    guard_rules = {}
    guard_fluents = set()
    for (t, g) in dawnet.guards().items():
        guard_rules[t] = guard_to_rules(t, g)
        for (head, body) in guard_rules[t]:
            guard_fluents.add(head)

    ctx = {
        'dawnet': dawnet,
        'nodata': nodata,
        'name': dawnet.name(),
        'transitions': dawnet.transitions(),
        'places': dawnet.placeNames(),
        'variables': dawnet.variableNames(),
        'guard_rules': guard_rules,
        'guard_fluents': guard_fluents,
        'start_place': dawnet.startPlace(),
        'end_place': dawnet.endPlace(),
        'lang': 'coala'
    }

    if stream:
        template.stream(ctx).dump(stream)
    else:
        return template.render(ctx)


def run_coala(source_path, workdir, outfile,
              timeout=None,
              horizon=20,
              cmd=None):
    command = get_configuration('command', default=cmd)
    if cmd is None:
        command.extend(['--max_horizon', str(horizon)])
    command.append(source_path)
    if timeout is None:
        timeout = get_configuration('timeout', default=utils.get_main_conf('timeout'))

    utils.run_solver(command, stdout=outfile, timeout=timeout)


def process_model(dawnet,
                  outfile=sys.stdout,
                  solve=False,
                  horizon=20,
                  keep=False,
                  tempdir=None,
                  nodata=False,
                  encoding='easyEnc'):
    if solve:
        tdir = utils.tempdir(prefix='dawnets_coala_', dir=tempdir)
        logging.info("Temporary dir in {}".format(tdir))
        bcpath = os.path.join(tdir, '{}.bc'.format(dawnet.name()))
        with open(bcpath, 'w') as o:
            render_dawnets_coala(dawnet, nodata=False, encoding=encoding, stream=o)
        run_coala(bcpath, tdir, outfile, horizon=horizon)
        if not keep:
            shutil.rmtree(tdir)
    else:
        render_dawnets_coala(dawnet, nodata=False, encoding=encoding, stream=outfile)


def main(stream):
    print(render_dawnets_coala(dawnet.readDAWNET(stream)))


if __name__ == '__main__':
    main(file(sys.argv[1], 'r'))
