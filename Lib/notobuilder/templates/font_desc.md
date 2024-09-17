Noto is a global font collection for writing in all modern and ancient languages.
{%if stub%}
    {{stub}}
{%else%}
    {{ family_name }} is
    {% include 'design.md' %}
    {%if is_UI%}
        for app and website user interfaces
    {%else%}
        for texts
    {%endif%}
    {%if scripts %}
        in the 
        {%- set primary_script =  scripts_info[scripts[0]] %}
        {%- if primary_script.historical%} historical {%endif%}
        {%- if primary_script.fictional%} fictional {%endif%}
        _{{- primary_script.name }}_ script
        {%- if scripts | length > 1%}
            and in
            {% for script in scripts[1:] %}
                {{scripts_info[script].name }}{{ ", " if not loop.last else "" }}
            {% endfor %}
        {% endif %}
    {%else%}
        that use {{blocks | join(", ")}}
    {%endif%}.
{%endif%}
It has
{% if axes %}
    {{ axes }} and
{% endif %}
{{"{:,}".format(glyphs_count) }} glyphs.
