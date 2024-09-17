{%if stub %}{{stub}}{% else %}
{{- family_name }} is {%- include "design.md" %}{{desc_scripts}}.{% endif %}

{{ family_name }} {%if axes%}has {{axes}}, {%endif%}contains {{ "{:,}".format(glyphs_count) }} glyphs,
{%- if features_count%} {{ "{:,}".format(features_count) }} OpenType features,{% endif %}
and supports {{ "{:,}".format(unicodes_count) }} characters
{%- if blocks|length > 1%} from {{blocks|length}} Unicode blocks:
{%- elif blocks|length == 1%} from the Unicode block
{%endif%} {{ blocks|join(', ') }}.

{%if scripts %}

### Supported writing systems

{% for script in scripts %}

#### {{scripts_info[script].name}}

{{scripts_info[script].summary}}

{{ script_description -}} Read more on
<a href="https://scriptsource.org/scr/{{script}}">ScriptSource</a>,
<a href="https://en.wikipedia.org/wiki/ISO_15924:{{script}}">Wikipedia</a>,
<a href="https://r12a.github.io/scripts/links?iso={{script}}">r12a</a>.
{% endfor %}

{%endif %}
