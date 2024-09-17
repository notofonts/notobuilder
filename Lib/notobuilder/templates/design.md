 {% if style == "Serif" %}a modulated (“serif”){%- elif style == "Sans" %}an unmodulated (“sans-serif”){%- else %}a {{ style }}{%- endif %}
{%- if is_mono %} monospaced{%- endif %} design 
{%- if variant %} in the {{ variant }} variant{% endif %}