
(define (problem {{ name }}) 

  (:domain {{ domain }})

  (:objects )

  (:init
      {% for fact in init %}
      {{ sexp2string(fact) }}
      {% endfor %}
  )

  (:goal 
    {% if goal is sequence and goal[0] in ('and') %}
    ({{ goal[0] }}
      {% for term in goal[1:] %}
      {{ sexp2string(term) }}
      {% endfor %}
    )
    {% else %}
    {{ sexp2string(goal) }}
    {% endif %}
  )
)
