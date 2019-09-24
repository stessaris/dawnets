#!/usr/bin/env python

"""\
Transform a DAWNet file into a PDDL planning problem
"""

from builtins import range
from builtins import object
import os
import sys
import logging
import pprint
import re
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import shutil
from dawnet.parser.dawnet import readDAWNET
from dawnet import utils


def get_configuration(option, default=None):
    section = 'pddl'
    default_values = {
        'command': 'fast-downward --alias seq-sat-lama-2011',
        'timeout': '0'
    }

    optvalue = utils.get_conf(section, option, default, default_values)

    if option == 'command':
        return utils.conf_shell_list(optvalue)
    elif option == 'timeout':
        return utils.conf_integer(optvalue)
    else:
        return optvalue


# PDDL types

PDDL_PLACE_TYPE = 'place'
PDDL_TRANSITION_TYPE = 'transition'
PDDL_AD_TYPE = 'active_domain'

# PDDL predicates

PDDL_ENABLED_PRED = 'p_enabled'
PDDL_TERMINAL_PRED = 'p_terminal'

# PDDL constants

PDDL_NULL_CONST = 'nullv'


def PDDL_VARIABLE_PRED(name):
    return name


def PDDL_VAR_DOMAIN_PRED(name):
    return 'dom_{}_rst'.format(name)


def PDDL_OLD_VALUE_VAR(varname):
    return 'past_' + varname


class PDDL(object):

    # see https://stackoverflow.com/questions/1323364/in-python-how-to-check-if-a-string-only-contains-certain-characters
    @staticmethod
    def _checkName(name, search=re.compile(r'[^a-zA-Z0-9_-]').search):
        return name and name[0].isalpha() and (not bool(search(name)))

    @staticmethod
    def id(name):
        sanitised = str(name).strip("'").replace(' ', '_')
        assert PDDL._checkName(sanitised), "Invalid PDDL name '{}'".format(sanitised)
        return sanitised

    @staticmethod
    def predicate_def(pname, *args):
        return (pname, args)

    @staticmethod
    def variable(name):
        return '?' + name

    @staticmethod
    def sexp(op, *args):
        return [op] + list(args)

    @staticmethod
    def const(obj):
        sanitised = str(obj).strip("'").replace(' ', '_')
        if sanitised[0].isdigit():
            logging.warning("Prepending 'v' to numeric constant {}".format(sanitised))
            sanitised = 'v' + sanitised
        assert PDDL._checkName(sanitised), "Invalid PDDL name '{}'".format(str(obj))
        return sanitised

    @staticmethod
    def atomic(predicate, *args):
        return PDDL.sexp(predicate, *args)

    @staticmethod
    def notExpr(arg):
        return PDDL.sexp('not', arg)

    @staticmethod
    def andExpr(*args):
        assert args
        return PDDL.sexp('and', *args) if len(args) > 1 else args[0]

    @staticmethod
    def orExpr(*args):
        assert args
        return PDDL.sexp('or', *args) if len(args) > 1 else args[0]

    @staticmethod
    def forallExpr(variables, gd):
        return PDDL._quantifier('forall', variables, gd)

    @staticmethod
    def existsExpr(variables, gd):
        return PDDL._quantifier('exists', variables, gd)

    @staticmethod
    def _quantifier(quant, variables, gd):
        if not variables:
            return gd
        else:
            for i in range(len(variables)):
                gvar, gvalues = variables[i]
                if not isinstance(gvalues, str if sys.version_info[0] >= 3 else basestring):
                    assert gvalues  # not empty list
                    sub_gd = PDDL._quantifier(quant, variables[i + 1:], gd)
                    grouded_gds = [PDDL._ground_var(gvar, val, sub_gd) for val in gvalues]
                    ggd = PDDL.orExpr(*grouded_gds) if quant == 'exists' else PDDL.andExpr(*grouded_gds)
                    return PDDL.sexp(quant, variables[:i], ggd) if i > 0 else ggd
            return PDDL.sexp(quant, variables, gd)

    @staticmethod
    def _ground_var(varname, val, gd):

        def isBound(var, decl):
            for v, dom in decl:
                if v == var:
                    return True
            return False

        if gd == varname:
            return val
        elif isinstance(gd, list):
            assert gd
            op = gd[0]
            if (op in ('forall', 'exists')) and isBound(varname, gd[1]):
                return gd
            else:
                return [op] + [PDDL._ground_var(varname, val, term) for term in gd[1:]]
        else:
            return gd

    @staticmethod
    def sexp2string(sexp, indent=0, nl=False):
        if isinstance(sexp, tuple) and len(sexp) == 2:
            return "{} - {}".format(sexp[0], sexp[1])
        elif isinstance(sexp, str if sys.version_info[0] >= 3 else basestring):
            return sexp
        elif isinstance(sexp, (list, tuple)):
            return "(" + " ".join([PDDL.sexp2string(t, indent=0, nl=nl) for t in sexp]) + ")"
        else:
            return str(sexp)


def guard2PDDL(dawnet, guard, variables=set()):

    def equal_values(lvar, rvar, variables):
        pddlvar = PDDL.variable(PDDL_OLD_VALUE_VAR(lvar))
        return (
            PDDL.andExpr(
                PDDL.notExpr(PDDL.atomic(PDDL_VARIABLE_PRED(lvar), PDDL_NULL_CONST)),
                PDDL.atomic(PDDL_VARIABLE_PRED(lvar), pddlvar),
                PDDL.atomic(PDDL_VARIABLE_PRED(rvar), pddlvar)
            ), variables.union([lvar]))

    def different_values(lvar, rvar, variables):
        pddlvar = PDDL.variable(lvar)
        return (
            PDDL.orExpr(
                PDDL.notExpr(PDDL.atomic(PDDL_VARIABLE_PRED(lvar), PDDL_NULL_CONST)),
                PDDL.andExpr(
                    PDDL.atomic(PDDL_VARIABLE_PRED(lvar), pddlvar),
                    PDDL.notExpr(PDDL.atomic(PDDL_VARIABLE_PRED(rvar), pddlvar))
                )
            ),
            variables.union([lvar])
        )

    if guard.isOR() or guard.isAND():
        args = []
        ovars = set()
        for term in guard.getArguments():
            expr, newvars = guard2PDDL(dawnet, term)
            ovars.update(newvars)
            args.append(expr)
        return (PDDL.orExpr(*args) if guard.isOR() else PDDL.andExpr(*args), variables.union(ovars))
    elif guard.isComparison():
        if guard.getOperator() == '=':
            if dawnet.isVariable(guard.rhs()):
                return equal_values(guard.lhs(), guard.rhs(), variables)
            else:
                return (PDDL.atomic(PDDL_VARIABLE_PRED(guard.lhs()), PDDL.const(guard.rhs())), variables)
        elif guard.getOperator() == '!=' or guard.getOperator() == '<>':
            if dawnet.isVariable(guard.rhs()):
                return different_values(guard.lhs(), guard.rhs(), variables)
            else:
                return (PDDL.notExpr(
                    PDDL.atomic(PDDL_VARIABLE_PRED(guard.lhs()), PDDL.const(guard.rhs()))), variables)
        else:
            logging.error("Unsupported operator in {}{}{}".format(guard.lhs(), guard.getOperator(), guard.rhs()))
    else:
        return (PDDL.const(guard), variables)


def PDDL_domain(dawnet):

    def delete_var_value(varname):
        return PDDL.notExpr(
            PDDL.atomic(PDDL_VARIABLE_PRED(varname), PDDL.variable(PDDL_OLD_VALUE_VAR(varname)))
        )

    def action_def(tname):
        update_vars = set()
        old_value_vars = set()

        preconditions = []
        for ip in dawnet.inflows(tname):
            preconditions.append(PDDL.atomic(PDDL_ENABLED_PRED, ip))
        if dawnet.hasGuard(tname):
            precond, ovars = guard2PDDL(dawnet, dawnet.guardObj(tname))
            preconditions.append(precond)
            old_value_vars.update(ovars)

        effects = []
        # outflows to true
        for op in dawnet.outflows(tname):
            effects.append(PDDL.atomic(PDDL_ENABLED_PRED, op))
        # inflows to false
        for ip in dawnet.inflows(tname):
            if ip not in dawnet.outflows(tname):
                effects.append(PDDL.notExpr(PDDL.atomic(PDDL_ENABLED_PRED, ip)))
        # updates
        for (varname, values) in dawnet.updates(tname).items():
            old_value_vars.add(varname)
            # delete all values to ensure functionality
            preconditions.append(PDDL.atomic(
                PDDL_VARIABLE_PRED(varname),
                PDDL.variable(PDDL_OLD_VALUE_VAR(varname))
            ))
            effects.append(delete_var_value(varname))

            # update the values
            if len(values) > 0:
                if len(values) > 1:
                    # if variable should be undefined the PDDL variable is not necessary
                    update_vars.add(varname)
                    preconditions.append(PDDL.atomic(
                        PDDL_VAR_DOMAIN_PRED(varname),
                        tname,
                        PDDL.variable(varname)
                    ))
                effects.append(
                    PDDL.atomic(
                        PDDL_VARIABLE_PRED(varname),
                        PDDL.variable(varname) if len(values) > 1 else PDDL.const(values[0]))
                )
            else:
                # empty set, delete value
                effects.append(
                    PDDL.atomic(PDDL_VARIABLE_PRED(varname), PDDL_NULL_CONST)
                )

        parameters = [(PDDL.variable(varname), PDDL_AD_TYPE) for varname in update_vars]
        parameters.extend((PDDL.variable(PDDL_OLD_VALUE_VAR(varname)), PDDL_AD_TYPE) for varname in old_value_vars)

        return {
            ':name': tname,
            ':parameters': parameters,
            ':precondition': PDDL.andExpr(*preconditions) if preconditions else [],
            ':effect': PDDL.andExpr(*effects) if effects else []
        }

    domain = {}

    domain[':name'] = PDDL.id(dawnet.name())
    domain[':requirements'] = [':adl']
    domain[':types'] = [PDDL_PLACE_TYPE, PDDL_TRANSITION_TYPE, PDDL_AD_TYPE]
    domain[':constants'] = [
        (PDDL_TRANSITION_TYPE, [PDDL.const(tname) for tname in dawnet.transitionNames()]),
        (PDDL_PLACE_TYPE, [PDDL.const(pname) for pname in dawnet.placeNames()]),
        (PDDL_AD_TYPE, [PDDL_NULL_CONST])
    ]
    if len(dawnet.getAD()) > 0:
            domain[':constants'].append((PDDL_AD_TYPE, [PDDL.const(value) for value in dawnet.getAD()]))
    domain[':predicates'] = [
        PDDL.predicate_def(PDDL_ENABLED_PRED, ('?p', PDDL_PLACE_TYPE)),
        PDDL.predicate_def(PDDL_TERMINAL_PRED, ('?p', PDDL_PLACE_TYPE))
    ]
    for varname in dawnet.variableNames():
        domain[':predicates'].append(PDDL.predicate_def(PDDL_VARIABLE_PRED(varname), ('?v', PDDL_AD_TYPE)))
        domain[':predicates'].append(
            PDDL.predicate_def(PDDL_VAR_DOMAIN_PRED(varname), ('?t', PDDL_TRANSITION_TYPE), ('?v', PDDL_AD_TYPE)))

    actions = {}
    for tname in dawnet.transitionNames():
        actions[tname] = action_def(tname)
    domain[':actions'] = actions

    return domain


def PDDL_problem(dawnet):
    problem = {}

    problem[':name'] = PDDL.id(dawnet.name() + "-pb")
    problem[':domain'] = PDDL.id(dawnet.name())

    problem[':init'] = [
        PDDL.atomic(PDDL_ENABLED_PRED, dawnet.startPlace()),
        PDDL.atomic(PDDL_TERMINAL_PRED, dawnet.endPlace())
    ]
    for tname in dawnet.transitionNames():
        for (var, values) in dawnet.updates(tname).items():
            if len(values) > 1:
                for val in values:
                    if val in dawnet.getAD():
                        problem[':init'].append(
                            PDDL.atomic(PDDL_VAR_DOMAIN_PRED(var), tname, PDDL.const(val))
                        )

    for varname in dawnet.variableNames():
        problem[':init'].append(
            PDDL.atomic(PDDL_VARIABLE_PRED(varname), PDDL_NULL_CONST)
        )

    problem[':goal'] = PDDL.andExpr(
        PDDL.atomic(PDDL_ENABLED_PRED, dawnet.endPlace()),
        *[PDDL.notExpr(PDDL.atomic(PDDL_ENABLED_PRED, PDDL.const(place)))
            for place in dawnet.placeNames() if place != dawnet.endPlace()]
    )

    return problem


ENV = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')),
    trim_blocks=True,
    lstrip_blocks=True)

ENV.globals['sexp2string'] = PDDL.sexp2string


def renderDomain(domain, stream=sys.stdout):
    templ_name = "domain.pddl"
    try:
        template = ENV.get_template(templ_name)
    except TemplateNotFound:
        logging.error('missing template {}'.format(templ_name))
        pass

    template.stream({
        'name': domain[':name'],
        'types': domain[':types'],
        'constants': domain[':constants'],
        'predicates': domain[':predicates'],
        'requirements': domain[':requirements'],
        'actions': domain[':actions']
    }).dump(stream)


def renderProblem(problem, stream=sys.stdout):
    templ_name = "problem.pddl"
    try:
        template = ENV.get_template(templ_name)
    except TemplateNotFound:
        logging.error('missing template {}'.format(templ_name))
        pass

    template.stream({
        'name': problem[':name'],
        'domain': problem[':domain'],
        'init': problem[':init'],
        'goal': problem[':goal']
    }).dump(stream)


def render_dawnet_pddl(dawnet):
    domain = PDDL_domain(dawnet)
    problem = PDDL_problem(dawnet)
    renderDomain(domain)
    renderProblem(problem)


def run_pddl(domain, problem, workdir, outfile, timeout=None, cmd=None):
    command = get_configuration('command', default=cmd)
    command.append(domain)
    command.append(problem)
    if timeout is None:
        timeout = get_configuration('timeout', default=utils.get_main_conf('timeout'))

    utils.run_solver(command, stdout=outfile, timeout=timeout)


def process_model(dawnet,
                  outfile=sys.stdout,
                  solve=False,
                  keep=False,
                  outdir=None,
                  cmd=None):

    wdir = utils.tempdir(prefix='dawnets_pddl_', dir=outdir) if solve else outdir

    domain = PDDL_domain(dawnet)
    problem = PDDL_problem(dawnet)

    if wdir:
        # write domain and problem files
        domfile = os.path.join(wdir, domain[':name'] + '.pddl')
        pbfile = os.path.join(wdir, problem[':name'] + '.pddl')

        with open(domfile, 'w') as fp:
            renderDomain(domain, fp)
        with open(pbfile, 'w') as fp:
            renderProblem(problem, fp)

        if solve:
            run_pddl(domfile, pbfile, wdir, outfile, cmd=cmd)
            if not keep:
                shutil.rmtree(wdir)
    else:
        renderDomain(domain, outfile)
        renderProblem(problem, outfile)


def main(stream):
    dawnet = readDAWNET(stream)
    domain = PDDL_domain(dawnet)
    problem = PDDL_problem(dawnet)

    pprint.pprint(domain)
    pprint.pprint(problem)

    renderDomain(domain)
    renderProblem(problem)


if __name__ == '__main__':
    main(file(sys.argv[1], 'r'))
