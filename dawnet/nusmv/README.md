# nuSMV encoding

## Variables

* _places_ each place is a boolean variable
* _DAWNet variable_ each variable has the DAWNet domain with the additional `undef` constant
* `tr` transition firing in the current state, domain is the list of DAWNet transitions plus `tr_last` and `tr_ended`

## Macros

* `pre_`_transition_: true when the preconditions of the transition are satisfied in the current state
* `next_pre_`_transition_: true when the preconditions of the transition are satisfied in the next state
* `frame_ax_`_transition_: frame axiom for the transition
* `no_pre`: none of the preconditions is satisfied in the current state
* `no_next_pre`:  none of the preconditions is satisfied in the next state
* `tr_consistent`: the value of the preconditions in the current state is coherent with the transition in `tr`
* `next_tr_consistent`: the value of the preconditions in the next state is coherent with the transition in `next(tr)`
* `clean_termination`: all places but the sink are false