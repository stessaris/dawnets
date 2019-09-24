# Encapsulate (nu)SMV language

from builtins import object, super
import re
import sys
import os
import logging
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# SMV language constants
BOOLEAN = 'boolean'
NEXT_PRED = 'next'
TRUE = 'TRUE'
FALSE = 'FALSE'


# see https://stackoverflow.com/questions/1323364/in-python-how-to-check-if-a-string-only-contains-certain-characters
def _checkName(name, search=re.compile(r'[^a-zA-Z0-9_-]').search):
    return name and name[0].isalpha() and (not bool(search(name)))


def _checkConst(name, search=re.compile(r'[^a-zA-Z0-9_-]').search):
    return name and (name[0].isalpha() or name.isdigit()) and (not bool(search(name)))


def _valid_name(name):
    sanitised = str(name).strip("'").replace(' ', '_')
    assert _checkName(sanitised), "Invalid SMV name '{}'".format(sanitised)
    return sanitised


def _valid_const(name):
    sanitised = str(name).strip("'").replace(' ', '_')
    assert _checkConst(sanitised), "Invalid SMV constant '{}'".format(sanitised)
    return sanitised


def id(name):
    return Term(_valid_name(name))


def const(value):
    return Term(_valid_const(value))


def nextPred(name):
    return PredTerm(NEXT_PRED, [_valid_name(name)])


def termIsTrue(term):
    return eqAtom(term, const(TRUE))


def termIsFalse(term):
    return eqAtom(term, const(FALSE))


def eqAtom(lhs, rhs):
    return BinRelAtom('=', lhs, rhs)


def neqAtom(lhs, rhs):
    return BinRelAtom('!=', lhs, rhs)


def andF(*args):
    assert len(args) > 0
    if len(args) > 1:
        return And(args)
    else:
        return args[0]


def orF(*args):
    assert len(args) > 0
    if len(args) > 1:
        return Or(args)
    else:
        return args[0]


def formula2string(formula):
    return repr(formula)


class Formula(object):

    def _brackets(self, exclude=None):
        if exclude and not isinstance(self, exclude):
            return '(' + repr(self) + ')'
        else:
            return repr(self)

    def isTerm(self):
        return isinstance(self, Term)

    def isAtomic(self):
        return isinstance(self, (Term, Atom))

    def isAnd(self):
        return isinstance(self, And)

    def isOr(self):
        return isinstance(self, Or)

    def isCase(self):
        return isinstance(self, Case)


class And(Formula):
    def __init__(self, formulae):
        assert all(isinstance(f, Formula) for f in formulae)
        self._subfs = formulae

    def __repr__(self):
        return ' & '.join([f._brackets((Term, Atom, Not)) for f in self.subformulae])

    @property
    def subformulae(self):
        return self._subfs


class Or(Formula):
    def __init__(self, formulae):
        assert all(isinstance(f, Formula) for f in formulae)
        self._subfs = formulae

    def __repr__(self):
        return ' | '.join([f._brackets((Term, Atom, Not)) for f in self.subformulae])

    @property
    def subformulae(self):
        return self._subfs


class Not(Formula):
    def __init__(self, formula):
        self._subf = formula

    def __repr__(self):
        if isinstance(self.subformula, Not):
            return repr(self.subformula.subformula)
        else:
            return ' !' + self.subformula._brackets((Term, Atom))

    @property
    def subformula(self):
        return self._subf


class Implies(Formula):
    def __init__(self, lhs, rhs):
        self._lhs = lhs
        self._rhs = rhs

    def __repr__(self):
        return self.lhs._brackets((Term, Not, Atom)) + ' -> ' + self.rhs._brackets((Term, Not, Atom))

    @property
    def lhs(self):
        return self._lhs

    @property
    def rhs(self):
        return self._rhs


class In(Formula):
    def __init__(self, term, constants):
        self._term = term
        self._consts = constants

    def __repr__(self):
        return repr(self.term) + ' in {' + ', '.join([repr(c) for c in self.constants]) + '}'

    @property
    def term(self):
        return self._term

    @property
    def constants(self):
        return self._consts


class Case(Formula):
    def __init__(self, cases):
        self._cases = cases

    def __repr__(self):
        casestr = "case "
        for (pre, post) in self.cases:
            ls = pre._brackets((Term, Atom, Not))
            rs = post._brackets((Term, Atom, Not))
            casestr += ' {} : {};'.format(ls, rs)
        casestr += ' esac'
        return casestr

    @property
    def cases(self):
        return self._cases


class LTLQuant(Formula):
    def __init__(self, quantifier, formula):
        self._quant = quantifier
        self._subf = formula

    def __repr__(self):
        if isinstance(self.subformula, Not):
            return repr(self.subformula.subformula)
        else:
            return self.quantifier + ' ' + self.subformula._brackets((Term, Atom))

    @property
    def quantifier(self):
        return self._quant
    pass

    @property
    def subformula(self):
        return self._subf
    pass


class LTL_next(LTLQuant):
    """ X ( formula )
    """
    def __init__(self, formula):
        super().__init__('X', formula)


class LTL_glob(LTLQuant):
    """ G ( formula )
    """
    def __init__(self, formula):
        super().__init__('G', formula)


class LTL_finally(LTLQuant):
    """ F ( formula )
    """
    def __init__(self, formula):
        super().__init__('F', formula)


class Term(Formula):
    def __init__(self, name):
        self._term = name

    def __repr__(self):
        return str(self._term)


class PredTerm(Term):
    def __init__(self, pname, pargs):
        self._name = _valid_name(pname)
        self._args = [_valid_name(name) for name in pargs]

    def __repr__(self):
        return "{}({})".format(self._name, ','.join(self._args))


class Atom(Formula):
    pass


class BinRelAtom(Atom):
    def __init__(self, op, lhs, rhs):
        self._op = op
        self._lhs = lhs
        self._rhs = rhs

    @property
    def op(self):
        return self._op

    @property
    def lhs(self):
        return self._lhs

    @property
    def rhs(self):
        return self._rhs

    def __repr__(self):
        return "{}{}{}".format(self.lhs, self.op, self.rhs)


class TrueVal(Atom):
    def __init_(self):
        pass

    def __repr__(self):
        return TRUE


class FalseVal(Atom):
    def __init_(self):
        pass

    def __repr__(self):
        return FALSE


ENV = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')),
    trim_blocks=True,
    lstrip_blocks=True)

ENV.globals['formula2string'] = formula2string


def renderSMV(spec, stream=sys.stdout):
    templ_name = "nusmv_template.smv"
    try:
        template = ENV.get_template(templ_name)
    except TemplateNotFound:
        logging.error('missing template {}'.format(templ_name))
        pass

    # template expect a sequence of transitions
    trans = spec.get('trans', [])
    try:
        iter(trans)     # non-iterable throw an exception
    except:
        trans = [trans]
    template.stream({
        'module': spec.get('name', 'dawnet'),
        'var': spec.get('var', None),
        'define': spec.get('define', None),
        'init': spec.get('init', None),
        'trans': trans,
        'ltlspec': spec.get('ltlspec', None)
    }).dump(stream)
