---
name: jinja2-atomic-design
description: "Jinja2 + HTMX component patterns. Triggers on: jinja, html, template, macro, atom, molecule, htmx, ssr, tailwind, caller."
compatibility: "Jinja2 3+, HTMX 1.9+, jinja2-fragments."
---

# Jinja2 Atomic Design (HTMX + SSR)

## Core Directives

- **Location:** Reusable atoms/molecules go in `templates/common/partials/`. Domain-specific components go in `templates/{domain}/partials/`.
- **Styling:** Use Tailwind CSS utility classes. Control variants via internal dictionaries, do not pass arbitrary utility strings.
- **HTMX:** Favor standard forms + HTMX attributes (`hx-get`, `hx-post`, `hx-swap`, `hx-target`). Avoid custom JS.

## Pattern 1: Multi-Variant Atoms (Tailwind)

Never pass raw Tailwind classes for core styling. Use variant mappings and accept generic `hx_attrs`.

```jinja
{% macro button(text, variant='primary', hx_attrs={}) -%}
  {% set styles = {
    'primary': 'bg-blue-600 hover:bg-blue-700 text-white',
    'ghost': 'bg-transparent hover:bg-gray-100 text-gray-800'
  } %}

  <button class="btn {{ styles.get(variant, styles['primary']) }}"
    {% for attr, value in hx_attrs.items() %} {{ attr }}="{{ value }}" {% endfor %}>
    {{ text }}
  </button>
{%- endmacro %}

{# Usage: {{ button('Save', hx_attrs={'hx-post': '/save', 'hx-target': '#res'}) }} #}
```

## Pattern 2: Slot Composition (caller)

Use `caller()` when a component wraps arbitrary inner content. Do not pass HTML strings as macro parameters.

```jinja
{% macro card(title) -%}
  <div class="card border rounded-lg">
    <div class="card-header border-b p-4">{{ title }}</div>
    <div class="card-body p-4">
      {{ caller() }}
    </div>
  </div>
{%- endmacro %}

{# Usage: #}
{% call card(title='File Details') %}
  <p>Inner content here</p>
  {{ file_source_icon('youtube') }}
{% endcall %}
```

## Pattern 3: Global Context (with context)

For top-level organisms that genuinely need `request` or `current_user` (like Navbars), use `with context`. Do not prop-drill these objects through multiple layers.

```jinja
{% macro main_nav() %}
  <nav>
    <a href="/files" class="{% if '/files' in request.url.path %}active{% endif %}">Files</a>
  </nav>
{% endmacro %}

{# Usage in base.html.jinja #}
{% from 'common/partials/main_navigation.html.jinja' import main_nav with context %}
{{ main_nav() }}
```

## Pattern 4: HTMX Out-of-Band Swaps (Multiple Targets)

When one action updates multiple parts of the UI, use `jinja2-fragments` blocks and `hx-swap-oob="true"`.

```jinja
{# In the partial template returned by the backend #}

{% block status_pill %}
  <span id="status-{{ file.id }}" class="pill-approved">Approved</span>
{% endblock %}

{% block file_count %}
  <div id="file-count" hx-swap-oob="true">{{ total_files }} files</div>
{% endblock %}
```

## Anti-Patterns to Correct

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| Hardcoding logic in parameters: `{{ icon(color='text-red-500') }}` | Pass semantic variants: `{{ icon(variant='danger') }}` |
| Prop drilling: `{{ row(item, request, user) }}` | Use `{% from ... import ... with context %}` if global state is required |
| Heavy JS logic for loading states | Render `async_content(state='loading')` and let HTMX replace it |
| Writing inline `<svg>` in multiple files | Extract to `common/partials/icons.html.jinja` atom |
