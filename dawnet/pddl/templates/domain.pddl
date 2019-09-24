{% macro printSexp(obj) %}
{% if obj is sequence and obj[0] in ('and') %}
({{ obj[0] }}
  {% for term in obj[1:] %}
  {{ sexp2string(term) }}
  {% endfor %}
)
{% else %}
{{ sexp2string(obj) }}
{% endif %}
{% endmacro %}

(define (domain {{ name }})

  (:requirements {{ requirements|join(' ') }})

  (:types
    {% for tname in types %}
    {{ tname }}
    {% endfor %}
  )

  (:constants
    {% for type, values in constants %}
    {{ values|join(' ') }} - {{ type }}
    {% endfor %}
  )

  (:predicates
    {% for predname, args in predicates %}
    ({{ predname }} {% for var,type in args -%} {{ var }} - {{ type }} {% endfor -%})
    {% endfor %}
  )

  {% for action in actions.values() %}
  (:action {{ action[':name']}}
    :parameters ( {% for var,type in action[':parameters'] -%} {{ var }} - {{ type }} {% endfor -%} )
    :precondition
      {{ printSexp(action[':precondition'])|indent(width=6) }}
    :effect
      {{ printSexp(action[':effect'])|indent(width=6) }}
  )

  {% endfor %}
)
