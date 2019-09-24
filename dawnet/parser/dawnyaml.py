""" Tools for YAML serialised DAWNets
"""

import sys
import pkgutil
import logging
import pprint
import re
import random
import json
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from jsonschema import validate, ValidationError
from .. import utils


yaml_reader = YAML(typ='safe')
# prevent the anchors/aliases in dumps
# see Ruaml code <https://bitbucket.org/ruamel/yaml/src/default/representer.py>
yaml_reader.Representer.ignore_aliases = lambda *args: True


def get_data(resource):
    data = pkgutil.get_data(__package__, resource).decode()
    assert data, "Resource {} missing in package {}".format(resource, __package__)
    return data


DAWNETSCHEMA_FILE = get_data('dawnet-schema.json')
TRACESCHEMA_FILE = get_data('trace-schema.json')

DAWNETSCHEMA = yaml_reader.load(DAWNETSCHEMA_FILE)
TRACESCHEMA = yaml_reader.load(TRACESCHEMA_FILE)

DAWNET_TRASITIONS_KEY = 'transitions'
DAWNET_NAME_KEY = 'name'
DAWNET_INFLOWS_KEY = 'inflows'
DAWNET_OUTFLOWS_KEY = 'outflows'
DAWNET_UPDATES_KEY = 'updates'
DAWNET_GUARD_KEY = 'guard'

TRACE_MODEL_KEY = 'model'
TRACE_TRACE_KEY = 'trace'
TRACE_TRANSITION_KEY = 'transition'
TRACE_NAME_KEY = 'name'
TRACE_UPDATES_KEY = 'updates'


def load_yaml(stream):
    try:
        return yaml_reader.load(stream)
    except YAMLError as e:
        logging.error("Input is not an YAML/JSON file: {}".format(e.message))
        return {}


def load_json(stream):
    try:
        return json.load(stream)
    except ValueError as e:
        logging.error("Input is not an JSON file: {}".format(e.message))
        return {}


def load_obj(stream):
    return load_json(stream) if utils.conf_boolean(utils.get_main_conf('usejson')) else load_yaml(stream)


def write_yaml(yaml_obj, stream=sys.stdout):
    yaml_reader.dump(yaml_obj, stream)


def write_json(yaml_obj, stream=sys.stdout):
    json.dump(yaml_obj, stream)


def write_obj(yaml_obj, stream=sys.stdout):
    return write_json(yaml_obj, stream) if utils.conf_boolean(utils.get_main_conf('usejson')) else write_yaml(yaml_obj, stream)


def validate_obj(yaml_obj, json_schema):
    assert isinstance(yaml_obj, dict)
    try:
        validate(yaml_obj, json_schema)
    except ValidationError as e:
        logging.error("File is not schema compliant: {}".format(e.message))
        return False
    return True


def validate_dawnet(yaml_obj):
    if not validate_obj(yaml_obj, DAWNETSCHEMA):
        logging.error("Invalid DAWNet file.")
        return False
    return True


def validate_trace(yaml_obj):
    if not validate_obj(yaml_obj, TRACESCHEMA):
        logging.error("Invalid trace file.")
        return False
    return True


def readDAWNETobj(stream):
    dawnet = load_obj(stream)
    if not (dawnet is not None and validate_dawnet(dawnet)):
        raise ValueError("Not a proper DAWNet object.")
    return dawnet


def readTraceObj(stream):
    trace = load_obj(stream)
    if not (trace is not None and validate_trace(trace)):
        raise ValueError("Not a proper trace object.")
    return trace


def dawnet_yaml(name, transitions):
    return {DAWNET_NAME_KEY: name, DAWNET_TRASITIONS_KEY: transitions}


def trace_yaml(dawnet, trace=[], name=None):
    trace = {TRACE_MODEL_KEY: dawnet, TRACE_TRACE_KEY: trace}
    if name:
        trace[TRACE_NAME_KEY] = name
    return trace


def transition_yaml(inflows, outflows, updates=None, guard=None):
    transition = {DAWNET_INFLOWS_KEY: inflows, DAWNET_OUTFLOWS_KEY: outflows}
    if updates:
        transition[DAWNET_UPDATES_KEY] = updates
    if guard:
        transition[DAWNET_GUARD_KEY] = guard
    return transition


def model_variables(dawnet_yaml):
    variable_names = set()
    for tobj in dawnet_yaml[DAWNET_TRASITIONS_KEY].viewvalues():
        if DAWNET_UPDATES_KEY in tobj:
            variable_names.update(tobj[DAWNET_UPDATES_KEY].viewkeys())
    return variable_names


def model_name(dawnet_yaml):
    return dawnet_yaml.get(DAWNET_NAME_KEY, 'none')


def model_transitions(dawnet_yaml):
    return dawnet_yaml.get(DAWNET_TRASITIONS_KEY, {})


def trace_transitions(trace_yaml):
    return trace_yaml.get(TRACE_TRACE_KEY, [])


def trace_model(trace_yaml):
    return trace_yaml.get(TRACE_MODEL_KEY, '')


def trace_name(trace_yaml):
    return trace_yaml.get(TRACE_NAME_KEY, '')


def start_end_places(dawnet_yaml):
    """Return the pair (start, sink) places of the net.
    """
    no_end = set()
    no_start = set()
    for tobj in dawnet_yaml[DAWNET_TRASITIONS_KEY].viewvalues():
        no_end.update(tobj.get(DAWNET_INFLOWS_KEY, []))
        no_start.update(tobj.get(DAWNET_OUTFLOWS_KEY, []))

    start_places = no_end.difference(no_start)
    end_places = no_start.difference(no_end)

    assert len(start_places) < 2, "Too many start places {}".format(start_places) 
    assert len(start_places) > 0, "No start place"
    assert len(end_places) < 2, "Too many end places {}".format(end_places)
    assert len(end_places) > 0, "No end place"
    return (next(iter(start_places)), next(iter(end_places)))


def list_replace_id(lst, mapping):
    for index, item in enumerate(lst):
        if item in mapping:
            lst[index] = mapping[item]


def replace_places(dawnet_yaml, mapping):
    for transition in model_transitions(dawnet_yaml).viewvalues():
        list_replace_id(transition[DAWNET_INFLOWS_KEY], mapping)
        list_replace_id(transition[DAWNET_OUTFLOWS_KEY], mapping)


def copy_model(dawnet_yaml, model_name=None):
    def newID(name):
        return '{}_{}'.format(model_name, name) if model_name else name

    def copy_updates(updates):
        return {newID(vname): list(updates[vname]) for vname in updates.viewkeys()}

    def copy_guard(guard):
        def _tokenize(string, regexp=re.compile(r'([^a-zA-Z0-9\'"_-]+)')):
            """Quick and dirty tokenizer for DAWNet guards.
            """
            # see <https://stackoverflow.com/questions/398560/split-by-b-when-your-regex-engine-doesnt-support-it>
            return regexp.split(string)

        if isinstance(guard, str if sys.version_info[0] >= 3 else basestring):
            return ''.join([(newID(t) if t in dawnet_vars else t) for t in _tokenize(guard)])
        elif isinstance(guard, dict):
            return {pname: copy_guard(guard[pname]) for pname in guard.viewkeys()}
        else:
            logging.error("unexpected guard type: {}".format(guard))
            raise SystemExit()
        return guard

    def copy_transition(transition):
        newTrans = {}

        for (pname, pvalue) in transition.items():
            if pname == DAWNET_NAME_KEY:
                newTrans[pname] = newID(pvalue)
            elif pname == DAWNET_INFLOWS_KEY:
                newTrans[pname] = [newID(p) for p in pvalue]
            elif pname == DAWNET_OUTFLOWS_KEY:
                newTrans[pname] = [newID(p) for p in pvalue]
            elif pname == DAWNET_UPDATES_KEY:
                newTrans[pname] = copy_updates(pvalue)
            elif pname == DAWNET_GUARD_KEY:
                newTrans[pname] = copy_guard(pvalue)
            else:
                newTrans[pname] = pvalue

        return newTrans

    dawnet_vars = model_variables(dawnet_yaml)
    model = {}
    for (pname, pvalue) in dawnet_yaml.items():
        if pname == DAWNET_NAME_KEY:
            model[pname] = model_name if model_name else pvalue
        elif pname == DAWNET_TRASITIONS_KEY:
            model[pname] = {newID(tname): copy_transition(pvalue[tname]) for tname in pvalue.keys()}
        else:
            model[pname] = pvalue

    return model


def copy_trace(trace_yaml, model_name=None):
    def newID(name):
        return '{}_{}'.format(model_name, name) if model_name else name

    def copy_updates(updates):
        return {newID(vname): updates[vname] for vname in updates.viewkeys()}

    def copy_item(trace_item):
        new_item = {}
        for (pname, pvalue) in trace_item.viewitems():
            if pname == TRACE_TRANSITION_KEY:
                new_item[pname] = newID(pvalue)
            elif pname == TRACE_UPDATES_KEY:
                new_item[pname] = copy_updates(pvalue)
            else:
                new_item[pname] = pvalue
        return new_item

    trace = {}
    for (pname, pvalue) in trace_yaml.viewitems():
        if pname == TRACE_MODEL_KEY:
            trace[pname] = model_name
        elif pname == TRACE_TRACE_KEY:
            trace[pname] = [copy_item(ti) for ti in pvalue]
        else:
            trace[pname] = pvalue

    return trace


def routing_place(tp, blockID):
    return 'rp_{}_{}'.format(tp, blockID)


def routing_transition(tp, blockID):
    return 'rt_{}_{}'.format(tp, blockID)


def dawnet_sequential(dawnets, name):
    """Returns a new DAWNET model concatenating the models in the dawnets sequence
    """
    transitions = {}
    last_endp = None
    for dawnet in dawnets:
        if DAWNET_TRASITIONS_KEY in dawnet:
            (sp, ep) = start_end_places(dawnet)
            if last_endp:
                # replace starting place with previous ending place
                replace_places(dawnet, {sp: last_endp})
            transitions.update(dawnet[DAWNET_TRASITIONS_KEY])
            last_endp = ep
    return dawnet_yaml(name, transitions)


def dawnet_alternative(dawnets, blockID):
    """Returns a new DAWNET model as XOR of the models in the dawnets sequence
    """
    new_startp = routing_place('s', blockID)
    new_endp = routing_place('e', blockID)
    transitions = {}
    for dawnet in dawnets:
        transitions.update(dawnet[DAWNET_TRASITIONS_KEY])
        (sp, ep) = start_end_places(dawnet)
        snID = model_name(dawnet)
        transitions[routing_transition('xs', snID)] = transition_yaml([new_startp], [sp])
        transitions[routing_transition('xj', snID)] = transition_yaml([ep], [new_endp])
    return dawnet_yaml(blockID, transitions)


def dawnet_parallel(dawnets, blockID):
    """Returns a new DAWNET model parallelising the models in the dawnets sequence
    """
    transitions = {}
    sps = []
    eps = []
    for dawnet in dawnets:
        transitions.update(dawnet[DAWNET_TRASITIONS_KEY])
        (sp, ep) = start_end_places(dawnet)
        sps.append(sp)
        eps.append(ep)

    transitions[routing_transition('ps', blockID)] = transition_yaml([routing_place('s', blockID)], sps)
    transitions[routing_transition('pj', blockID)] = transition_yaml(eps, [routing_place('e', blockID)])
    return dawnet_yaml(blockID, transitions)


def trace_sequential(traces, model_name):
    """Concatenates the given traces
    """
    new_trace = []
    for trace in traces:
        new_trace.extend(trace[TRACE_TRACE_KEY])
    new_name = trace_name(traces[0])
    return trace_yaml(model_name, new_trace, name=new_name)


def trace_alternative(traces, model_name):
    """Randomly selects one of the alternative traces.
    """
    selected_trace = traces[random.randint(0, len(traces) - 1)]
    return trace_yaml(model_name, selected_trace[TRACE_TRACE_KEY], name=selected_trace[TRACE_NAME_KEY])


def trace_parallel(traces, model_name):
    """Parallelise the given traces.
    """
    new_trace = []
    trace_queue = [list(tr[TRACE_TRACE_KEY]) for tr in traces]
    while trace_queue:
        selected_trace_idx = random.randint(0, len(trace_queue) - 1)
        selected_trace = trace_queue[selected_trace_idx]
        if selected_trace:
            new_trace.append(selected_trace.pop(0))
        if len(selected_trace) < 1:
            trace_queue.pop(selected_trace_idx)
    new_name = trace_name(traces[0])
    return trace_yaml(model_name, new_trace, name=new_name)


def main(in_stream):
    yaml_obj = load_obj(in_stream)
    if (TRACE_MODEL_KEY in yaml_obj) and validate_trace(yaml_obj):
        pprint.pprint(copy_trace(yaml_obj, 'k0'))
    elif validate_dawnet(yaml_obj):
        new_model = copy_model(yaml_obj, 'k0')
        pprint.pprint(new_model)
        pprint.pprint(start_end_places(new_model))
    else:
        logging.error("Invalid input {} file".format(
            'trace' if (TRACE_MODEL_KEY in yaml_obj) else 'DAWNet'))


if __name__ == '__main__':
    main(file(sys.argv[1], 'r') if len(sys.argv) > 1 else sys.stdin)
