#!/usr/bin/env python

"""\
Transform a DAWNet file into a nuSMV model checking problem
"""

import sys
import logging
import shutil
import os
from . import SMV
from dawnet.parser.dawnet import readDAWNET
from collections import OrderedDict
from dawnet import utils

# Names to be used in the translation
SMV_TRANSITION_VAR = 'tr'
SMV_LAST_TR = 'tr_last'
SMV_ENDED_TR = 'tr_ended'
SMV_NO_PRE = 'no_pre'
SMV_NO_NEXT_PRE = 'no_next_pre'
SMV_TR_CONSISTENT = 'tr_consistent'
SMV_NEXT_TR_CONSISTENT = 'next_tr_consistent'
SMV_UNDEF_CONST = 'undef'
SMV_TERMINATION_COND = 'clean_termination'


def get_configuration(option, default=None):
    section = 'nusmv'
    default_values = {
        'expand_defs': 'False',
        'command': 'nuXsmv',
        'timeout': '0'
    }

    optvalue = utils.get_conf(section, option, default, default_values)

    if option == 'expand_defs':
        return utils.conf_boolean(optvalue)
    elif option == 'command':
        return utils.conf_shell_list(optvalue)
    elif option == 'timeout':
        return utils.conf_integer(optvalue)
    else:
        return optvalue


def precond_name(tname):
    return 'pre_' + tname


def next_precond_name(tname):
    return 'next_pre_' + tname


def frame_axiom_name(tname):
    return 'frame_ax_' + tname


def transitionEq(tname, nextState=False):
    smv_var = SMV.nextPred(SMV_TRANSITION_VAR) if nextState else SMV.id(SMV_TRANSITION_VAR)
    return SMV.eqAtom(smv_var, SMV.const(tname))


def transitionNeq(tname, nextState=False):
    smv_var = SMV.nextPred(SMV_TRANSITION_VAR) if nextState else SMV.id(SMV_TRANSITION_VAR)
    return SMV.neqAtom(smv_var, SMV.const(tname))


def frame_expr(name):
    return SMV.eqAtom(SMV.nextPred(name), SMV.id(name))


def guard2SMV(dawnet, guard, nextState=False):
    if guard.isOR():
        args = [guard2SMV(dawnet, term) for term in guard.getArguments()]
        return SMV.orF(*args)
    elif guard.isAND():
        args = [guard2SMV(dawnet, term) for term in guard.getArguments()]
        return SMV.andF(*args)
    elif guard.isComparison():
        lhs = SMV.nextPred(guard.lhs()) if nextState else SMV.id(guard.lhs())
        if dawnet.isVariable(guard.rhs()):
            rhs = SMV.nextPred(guard.rhs()) if nextState else SMV.id(guard.rhs())
        else:
            rhs = SMV.const(guard.rhs())
        if guard.getOperator() == '=':
            return SMV.eqAtom(lhs, rhs)
        elif guard.getOperator() == '!=' or guard.getOperator() == '<>':
            return SMV.neqAtom(lhs, rhs)
        else:
            logging.error("Unsupported operator in {}{}{}".format(guard.lhs(), guard.getOperator(), guard.rhs()))
    else:
        return SMV.const(guard)


def SMV_spec(dawnet, expandDefs=False):

    # SMV definitions
    definitions = OrderedDict()

    def id_or_def(name):
        return definitions[name] if expandDefs and name in definitions else SMV.id(name)

    def preconditions_SMV(tname, nextState=False):
        preconditions = []
        for ip in dawnet.inflows(tname):
            preconditions.append(
                SMV.termIsTrue(SMV.nextPred(ip) if nextState else SMV.id(ip)))
        if dawnet.hasGuard(tname):
            preconditions.append(guard2SMV(dawnet, dawnet.guardObj(tname), nextState))

        if len(preconditions) == 0:
            return SMV.TrueVal()
        else:
            return SMV.andF(*preconditions)

    def transition_SMV(tname):
        exprs = [id_or_def(SMV_NEXT_TR_CONSISTENT), id_or_def(frame_axiom_name(tname))]
        # outflows to true
        for op in dawnet.outflows(tname):
            exprs.append(SMV.termIsTrue(SMV.nextPred(op)))
        # inflows to false
        for ip in dawnet.inflows(tname):
            if ip not in dawnet.outflows(tname):
                exprs.append(SMV.termIsFalse(SMV.nextPred(ip)))
        # variable updates
        for (varname, values) in dawnet.updates(tname).items():
            if values:
                exprs.append(
                    SMV.In(SMV.nextPred(varname), [SMV.const(v) for v in values])
                )
            else:
                exprs.append(SMV.eqAtom(SMV.nextPred(varname), SMV.const(SMV_UNDEF_CONST)))

        if len(exprs) == 0:
            return SMV.TrueVal()
        else:
            return SMV.andF(*exprs)

    def ending_transition_SMV():
        exprs = [transitionEq(SMV_ENDED_TR, nextState=True)]
        for pid in dawnet.placeNames():
            exprs.append(SMV.termIsFalse(SMV.nextPred(pid)))
        for vid in dawnet.variableNames():
            exprs.append(SMV.eqAtom(SMV.nextPred(vid), SMV.const(SMV_UNDEF_CONST)))

        if len(exprs) == 0:
            return SMV.TrueVal()
        else:
            return SMV.andF(*exprs)

    def termination_expression():
        exprs = [SMV.termIsTrue(dawnet.endPlace())]
        for pid in dawnet.placeNames():
            if pid != dawnet.endPlace():
                exprs.append(SMV.termIsFalse(pid))

        if len(exprs) == 0:
            return SMV.TrueVal()
        else:
            return SMV.andF(*exprs)

    def transition_frame_axiom_SMV(tname):
        untouched_places = [p for p in dawnet.placeNames()
                            if p not in dawnet.inflows(tname) and p not in dawnet.outflows(tname)]
        untouched_vars = [v for v in dawnet.variableNames()
                          if v not in dawnet.updates(tname)]

        exprs = [frame_expr(f) for f in untouched_places]
        exprs += [frame_expr(f) for f in untouched_vars]

        if len(exprs) == 0:
            return SMV.TrueVal()
        else:
            return SMV.andF(*exprs)

    spec = dict()
    spec['name'] = 'main'       # fixed!

    vardefs = OrderedDict()
    # places
    for p in dawnet.placeNames():
        vardefs[SMV.id(p)] = SMV.BOOLEAN
    # transitions
    vardefs[SMV_TRANSITION_VAR] = [SMV_LAST_TR, SMV_ENDED_TR] + [
        SMV.const(tname) for tname in dawnet.transitionNames()
    ]
    # variables
    for vid in dawnet.variableNames():
        vardefs[SMV._valid_name(vid)] = [SMV_UNDEF_CONST] + list(dawnet.varDomain(vid))

    spec['var'] = vardefs

    # DEFINE

    for tname in dawnet.transitionNames():
        definitions[precond_name(tname)] = preconditions_SMV(tname)

    for tname in dawnet.transitionNames():
        definitions[next_precond_name(tname)] = preconditions_SMV(tname, nextState=True)

    # no precondition is tru in the current state
    def_exprs = [SMV.Not(id_or_def(precond_name(tname))) for tname in dawnet.transitionNames()]
    if def_exprs:
        definitions[SMV_NO_PRE] = SMV.andF(*def_exprs)

    # no precondition is tru in the next state
    def_exprs = [SMV.Not(id_or_def(next_precond_name(tname))) for tname in dawnet.transitionNames()]
    if def_exprs:
        definitions[SMV_NO_NEXT_PRE] = SMV.andF(*def_exprs)

    # preconditions are consistent with the current state transition
    def_exprs = [SMV.Implies(transitionEq(SMV_LAST_TR), id_or_def(SMV_NO_PRE)), transitionNeq(SMV_ENDED_TR)]
    for tname in dawnet.transitionNames():
        def_exprs.append(SMV.Implies(transitionEq(tname), id_or_def(precond_name(tname))))
    if def_exprs:
        definitions[SMV_TR_CONSISTENT] = SMV.andF(*def_exprs)

    # preconditions are consistent with the next state transition
    def_exprs = [
        SMV.Implies(transitionEq(SMV_LAST_TR, nextState=True), id_or_def(SMV_NO_NEXT_PRE)),
        SMV.Implies(transitionEq(SMV_ENDED_TR, nextState=True), transitionEq(SMV_LAST_TR))
    ]
    for tname in dawnet.transitionNames():
        def_exprs.append(SMV.Implies(transitionEq(tname, nextState=True), id_or_def(next_precond_name(tname))))
    if def_exprs:
        definitions[SMV_NEXT_TR_CONSISTENT] = SMV.andF(*def_exprs)

    # frame axioms
    for tname in dawnet.transitionNames():
        definitions[frame_axiom_name(tname)] = transition_frame_axiom_SMV(tname)

    # Termination condition
    definitions[SMV_TERMINATION_COND] = termination_expression()

    spec['define'] = definitions if not expandDefs else {}

    # INIT

    init_exprs = [SMV.termIsTrue(dawnet.startPlace())]
    for pid in dawnet.placeNames():
        if pid != dawnet.startPlace():
            init_exprs.append(SMV.termIsFalse(pid))
    for vid in dawnet.variableNames():
        init_exprs.append(SMV.eqAtom(SMV.id(vid), SMV.const(SMV_UNDEF_CONST)))

    init_exprs.append(id_or_def(SMV_TR_CONSISTENT))

    spec['init'] = SMV.andF(*init_exprs)

    # TRANS

    cases = []
    for tname in dawnet.transitionNames():
        head = transitionEq(tname)
        body = transition_SMV(tname)
        cases.append((head, body))
    # looping terminating transations
    cases.append(
        (SMV.orF(transitionEq(SMV_LAST_TR), transitionEq(SMV_ENDED_TR)),
            ending_transition_SMV()))

    spec['trans'] = SMV.Case(cases)

    # LTLSPEC

    #  G (!termination | tr=tr_ended)
    spec['ltlspec'] = SMV.LTL_glob(SMV.orF(
        SMV.Not(id_or_def(SMV_TERMINATION_COND)),
        transitionEq(SMV_ENDED_TR)
    ))

    return spec


def render_dawnet_smv(dawnet, stream=sys.stdout):
    expnd_defs = get_configuration('expand_defs')

    spec = SMV_spec(dawnet, expandDefs=expnd_defs)
    SMV.renderSMV(spec, stream)


def run_smv(source_path, workdir, outfile, timeout=None):
    command = get_configuration('command')
    command.append(source_path)
    if timeout is None:
        timeout = get_configuration('timeout', default=utils.get_main_conf('timeout'))

    utils.run_solver(command, stdout=outfile, timeout=timeout)


def process_model(dawnet,
                  outfile=sys.stdout,
                  solve=False,
                  keep=False,
                  tempdir=None):
    if solve:
        tdir = utils.tempdir(prefix='dawnets_smv_', dir=tempdir)
        logging.info("Temporary dir in {}".format(tdir))
        smvpath = os.path.join(tdir, '{}.smv'.format(dawnet.name()))
        with open(smvpath, 'w') as o:
            render_dawnet_smv(dawnet, o)
        run_smv(smvpath, tdir, outfile)
        if not keep:
            shutil.rmtree(tdir)
    else:
        render_dawnet_smv(dawnet, outfile)


def main(in_stream):
    dawnet = readDAWNET(in_stream)
    render_dawnet_smv(dawnet)


if __name__ == '__main__':
    main(file(sys.argv[1], 'r') if len(sys.argv) > 1 else sys.stdin)
