
""" DAWNets handling """

from builtins import object
from future.utils import with_metaclass
import abc
import os
import sys
import copy
import pprint
import logging
from textx.metamodel import metamodel_from_file
from textx.exceptions import TextXError
from . import dawnyaml
from .. import utils


# TextX schema for guards
GUARD_MM = metamodel_from_file(os.path.abspath(os.path.join(os.path.dirname(__file__), 'dawnet_guards_grammar.tx')))


def parse_guard(guard_expr):
    if guard_expr:
        try:
            # TextX requires unicode in Python < 3 
            #   (see <https://github.com/textX/textX/blob/00c0ec3a27c6aae051e63530be90eba0b3e8a90a/textx/metamodel.py#L22>)
            return GUARD_MM.model_from_str(str(guard_expr) if sys.version_info[0] >= 3 else unicode(guard_expr))
        except TextXError as e:
            logging.error("Error in guard [{}]: {}".format(guard_expr, e))
            return None
    else:
        return None


def guard_parse_tree(g_model):
    tname = type(g_model).__name__
    if tname == 'Guard':
        return {'type': tname, 'expr': guard_parse_tree(g_model.expr)}
    elif tname == 'And_expr':
        return {'type': tname,
                'terms': [guard_parse_tree(term) for term in g_model.terms]}
    elif tname == 'Or_expr':
        return {'type': tname,
                'terms': [guard_parse_tree(term) for term in g_model.terms]}
    elif tname == 'Parens_expr':
        return {'type': tname, 'expr': guard_parse_tree(g_model.expr)}
    elif tname == 'Comparison':
        return {'type': tname,
                'op': g_model.op,
                'lhs': guard_parse_tree(g_model.lhs),
                'rhs': guard_parse_tree(g_model.rhs)}
    elif tname == 'Truth':
        return {'type': tname, 'value': g_model.value}
    elif tname == 'Var':
        return {'type': tname, 'value': g_model.id}
    elif tname == 'Const':
        return {'type': tname, 'value': str(g_model.value)}
    else:
        logging.error('unknown guard "{}" of category {}'.format(str(g_model), tname))
        return {'type': tname, 'value': str(g_model)}


def check_guard(guard_expr):
    def sexp(op, args):
        return {'op': op, 'args': args}

    def simplify_guard(g_expr):
        tname = type(g_expr).__name__
        if tname == 'Guard':
            return simplify_guard(g_expr.expr)
        elif tname == 'And_expr':
            if len(g_expr.terms) > 1:
                return ANDexpr([simplify_guard(ge) for ge in g_expr.terms])
            else:
                return simplify_guard(g_expr.terms[0])
        elif tname == 'Or_expr':
            if len(g_expr.terms) > 1:
                return ORexpr([simplify_guard(ge) for ge in g_expr.terms])
            else:
                return simplify_guard(g_expr.terms[0])
        elif tname == 'Parens_expr':
            return simplify_guard(g_expr.expr)
        elif tname == 'Comparison':
            return Comparison(g_expr.op, simplify_guard(g_expr.lhs), simplify_guard(g_expr.rhs))
        elif tname == 'Truth':
            return Truthvalue(g_expr.value)
        elif tname == 'Var':
            return g_expr.id
        elif tname == 'Const':
            return "'{}'".format(str(g_expr.value))
        else:
            logging.error('unknown guard "{}" of category {}'.format(str(g_expr), tname))

    guard_model = parse_guard(guard_expr)
    return simplify_guard(guard_model) if guard_model else None


def ORexpr(args):
    terms = []
    for arg in args:
        if arg is not None:
            if arg.isOR():
                terms += arg.getArguments()
            elif isinstance(arg, Truthvalue):
                if arg.isTrue():
                    return Truthvalue('true')
            else:
                terms.append(arg)
    if len(terms) < 1:
        return Truthvalue('true')
    elif len(terms) == 1:
        return terms[0]
    else:
        return Or(terms)


def ANDexpr(args):
    terms = []
    for arg in args:
        if arg is not None:
            if arg.isAND():
                terms += arg.getArguments()
            elif isinstance(arg, Truthvalue):
                if arg.isFalse():
                    return Truthvalue('false')
            else:
                terms.append(arg)
    if len(terms) < 1:
        return Truthvalue('false')
    elif len(terms) == 1:
        return terms[0]
    else:
        return And(terms)


class Guard(with_metaclass(abc.ABCMeta, object)):

    _op = None
    _args = []

    def isOR(self):
        return self._op == 'OR'

    def isAND(self):
        return self._op == 'AND'

    def isComparison(self):
        return isinstance(self, Comparison)

    def isTruthValue(self):
        return isinstance(self, Truthvalue)

    def isAtom(self):
        return not (self.isAND() or self.isOR())

    def getArguments(self):
        return self._args

    def getOperator(self):
        return self._op

    def prefixExpr(self):
        if isinstance(self, Comparison):
            return '{}({}, {})'.format(self.getOperator(), self.getArguments()[0], self.getArguments()[1])
        elif isinstance(self, Truthvalue):
            return self.getOperator()
        else:
            return '{}({})'.format('And' if self.isAND() else 'Or', ', '.join([arg.prefixExpr() for arg in self.getArguments()]))

    @staticmethod
    def isConst(term):
        strTerm = str(term)
        return strTerm[0] == "'" and strTerm[-1] == "'"

    @staticmethod
    def constName(term):
        return str(term).strip("'").replace(' ', '_')

    @abc.abstractmethod
    def getConstants(self):
        """Returns the set of contants referred within the guard."""
        pass


class And(Guard):
    def __init__(self, args):
        self._op = 'AND'
        self._args = args

    def __repr__(self):
        return '(' + ' & '.join([pprint.pformat(e) for e in self.getArguments()]) + ')'

    def getConstants(self):
        return set().union(*[s.getConstants() for s in self.getArguments()])


class Or(Guard):
    def __init__(self, args):
        self._op = 'OR'
        self._args = args

    def __repr__(self):
        return '(' + ' | '.join([pprint.pformat(e) for e in self.getArguments()]) + ')'

    def getConstants(self):
        return set().union(*[s.getConstants() for s in self.getArguments()])


class Truthvalue(Guard):
    def __init__(self, value):
        self._op = 'true' if value.lower() == 'true' else 'false'

    def __repr__(self):
        return self._op

    def isTrue(self):
        return self._op == 'true'

    def isFalse(self):
        return not self.isTrue()

    def getConstants(self):
        return set()


class Comparison(Guard):
    def __init__(self, op, lhs, rhs):
        self._op = op
        self._args = [lhs, rhs]

    def __repr__(self):
        return '{}{}{}'.format(self.getArguments()[0], self.getOperator(), self.getArguments()[1])

    def lhs(self):
        return self._args[0]

    def rhs(self):
        return self._args[1]

    def getConstants(self):
        # WARNING: it might return variable names
        return set([Guard.constName(x) for x in self.getArguments()])


def readDAWNET(stream):
    dawnet_obj = dawnyaml.readDAWNETobj(stream)
    return DAWNet(dawnet_obj) if dawnet_obj is not None else None


def readTrace(stream):
    return dawnyaml.readTraceObj(stream)


def getGuardExpr(tobj, lang='default'):
    guard_obj = tobj.get('guard', {})
    if isinstance(guard_obj, dict):
        guard_obj.get(lang, None)
    else:
        return guard_obj if lang == 'default' else None


class DAWNet(object):

    @staticmethod
    def reduced_domain_flag():
        return utils.get_main_conf('reducedomain', type=bool)

    @staticmethod
    def nodata_flag():
        return utils.get_main_conf('nodata', type=bool)

    def __init__(self, dawnetOBJ):
        self._json_obj = dawnetOBJ if isinstance(dawnetOBJ, dict) else dict()
        self._name = dawnetOBJ.get('name', 'DAWNet')
        self._transitions = self._json_obj.get('transitions', {})
        self._place_adj = {}
        self._place_insets = {}
        self._vars = {}
        self._guards = {}
        self._ad = set()
        self._guardConsts = set()
        for (name, t) in self._transitions.items():
            self._updateTransitionInstance(name, t)
        self.updateStartEndPlaces()

    def _updateTransitionInstance(self, name, tobj):
        for p in tobj['outflows']:
            if p not in self._place_adj:
                self._place_adj[p] = set()
            if p not in self._place_insets:
                self._place_insets[p] = set()
            self._place_insets[p].add(name)
        for p in tobj['inflows']:
            if p not in self._place_adj:
                self._place_adj[p] = set()
            if p not in self._place_insets:
                self._place_insets[p] = set()
            self._place_adj[p].add(name)
        for (v, obs) in tobj.get('updates', {}).items():
            # make sure update values are strings
            v_values = set([str(o) for o in obs])
            self._ad.update(v_values)
            if v in self._vars:
                self._vars[v] = self._vars[v] | v_values
            else:
                self._vars[v] = v_values
        guard = check_guard(getGuardExpr(tobj))
        if guard:
            self._guards[name] = guard
            self._guardConsts.update(guard.getConstants())
        # Guard getConstants might return variable names
        self._guardConsts.difference_update(self.variableNames())

    def updateStartEndPlaces(self):
        startPlaces = [name for (name, trSet) in self._place_insets.items() if len(trSet) < 1]
        if len(startPlaces) > 1:
            logging.error('Too many start places {}.'.format(', '.join(startPlaces)))
        if len(startPlaces) < 1:
            logging.error('Missing start place.')
        self._start = startPlaces[0] if len(startPlaces) > 0 else None
        endPlaces = [name for (name, trSet) in self._place_adj.items() if len(trSet) < 1]
        if len(endPlaces) > 1:
            logging.error('Too many end places {}.'.format(', '.join(endPlaces)))
        if len(endPlaces) < 1:
            logging.error('Missing end place.')
        self._end = endPlaces[0] if len(endPlaces) > 0 else None

    def getSummary(self):
        dawnetDesc = {
            'Transitions': self.transitionNames(),
            'Places': self.placeNames(), 'start place': self.startPlace(), 'end place': self.endPlace(),
            'Vars': {v: list(self.varDomain(v)) for v in self.variableNames()},
            'Guards': {key: str(guard) for (key, guard) in self.guards().items()},
            'Guard Consts': list(self.getGuardConst()),
            'Active domain': list(self.getAD()),
            'Full domain': list(self._ad)
        }
        return dawnetDesc

    def show(self):
        dawnyaml.write_yaml(self.getSummary())

    def toYAML(self, stream):
        dawnetOBJ = {'name': self.name(), 'transitions': self.transitions()}
        dawnyaml.write_yaml(dawnetOBJ, stream)

    def transitions(self):
        return self._transitions

    def guards(self):
        return {} if self.nodata_flag() else self._guards

    def name(self):
        return self._name

    def startPlace(self):
        return self._start

    def endPlace(self):
        return self._end

    def transitionNames(self):
        return self._transitions.keys()

    def placeNames(self):
        return self._place_adj.keys()

    def variableNames(self):
        return [] if self.nodata_flag() else self._vars.keys()

    def varDomain(self, name):
        return self._vars[name].intersection(self.getAD())

    def getAD(self):
        if self.nodata_flag():
            return set()
        elif self.reduced_domain_flag():
            return self.getGuardConst()
        else:
            return self._ad

    def getGuardConst(self):
        return set() if self.nodata_flag() else self._guardConsts

    def isVariable(self, name):
        return name in self._vars

    def inflows(self, transition):
        return self._transitions.get(transition, {}).get('inflows', [])

    def outflows(self, transition):
        return self._transitions.get(transition, {}).get('outflows', [])

    def updates(self, transition):
        if self.nodata_flag():
            return {}
        elif self.reduced_domain_flag():
            reduced_updates = {}
            for var, values in self._transitions.get(transition, {}).get('updates', {}).items():
                reduced_values = [value for value in values if value in self.getAD()]
                if not (len(reduced_values) == 0 and len(values) > 0):
                    # when all the update values have been removed then
                    #   variable shouldn't be touched
                    reduced_updates[var] = reduced_values
            return reduced_updates
        else:
            return self._transitions.get(transition, {}).get('updates', {})

    def guard(self, transition):
        return None if self.nodata_flag() else self._transitions.get(transition, {}).get('guard', None)

    def guardExpr(self, transition, lang='default'):
        return None if self.nodata_flag() else getGuardExpr(self._transitions.get(transition, {}), lang)

    def guardObj(self, transition):
        return self.guards().get(transition, None)

    def hasGuard(self, transition):
        return False if self.nodata_flag() else transition in self.guards()

    def newTransition(self, name, inflows, outflows, guard=None, updates=None):
        tobj = {'inflows': inflows, 'outflows': outflows}
        if updates:
            tobj['updates'] = updates
        if guard:
            tobj['guard'] = guard
        self._transitions[name] = tobj
        # pprint.PrettyPrinter(indent=2).pprint(tobj)
        self._updateTransitionInstance(name, tobj)
        return tobj


def embed_trace(dawnet, trace):
    class WrongTransition(Exception):
        pass

    def stepName(step):
        return 'tr_stp{}'.format(step)

    def trName(name, step):
        return 'tr_{}_{}'.format(name, step)

    # make a copy of the original DAWNet
    ext_dawnet = copy.deepcopy(dawnet)

    # See file:trace-schema.json for expected format of a trace
    trace_step = 0
    for log_item in trace['trace']:
        tr_name = log_item['transition']
        try:
            if tr_name not in ext_dawnet.transitions():
                raise WrongTransition('transition {} is not in the model'.format(tr_name))
            tr_updates = ext_dawnet.updates(tr_name)
            updates = {}
            if 'updates' in log_item:
                for (varname, varvalue) in log_item['updates'].items():
                    # if (str(varvalue) in ext_dawnet.updates(tr_name).get('varname', [])):
                    if (varname in tr_updates and str(varvalue) in tr_updates[varname]):
                        updates[varname] = [str(varvalue)]
                    else:
                        logging.warning('Dropping update {}:{} for transition {}'.format(varname, varvalue, tr_name))
            inflows = list(ext_dawnet.inflows(tr_name))
            inflows.append(stepName(trace_step))
            trace_step += 1
            outflows = list(ext_dawnet.outflows(tr_name))
            outflows.append(stepName(trace_step))
            guard = ext_dawnet.guard(tr_name)
            ext_dawnet.newTransition(trName(tr_name, trace_step), inflows, outflows, guard, updates if len(updates.keys()) > 0 else None)
        except WrongTransition as e:
            logging.error('Dropping transition {}: {}'.format(tr_name, e))

    if trace_step > 0:
        # Add new start and end places
        ext_dawnet.newTransition(trName('start', ''), [trName('pstart', '')], [stepName(0), ext_dawnet.startPlace()])
        ext_dawnet.newTransition(trName('end', ''), [stepName(trace_step), ext_dawnet.endPlace()], [trName('pend', '')])
        ext_dawnet.updateStartEndPlaces()

    return ext_dawnet
