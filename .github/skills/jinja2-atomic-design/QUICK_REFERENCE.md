# Jinja2 Atomic Design - Quick Reference

## Component Template

```jinja
{# templates/[common|{domain}]/partials/component_name.html.jinja #}
{#
  Atomic Component: Component Name
  Category: Atom | Molecule | Organism

  Purpose: One-line description

  Composed of: (for Molecules/Organisms)
    - atom_component (atom)
    - molecule_component (molecule)

  Usage:
    {% from 'path/to/component.html.jinja' import component_name %}
    {{ component_name(param='value') }}

  Parameters:
    - param1 (type): Description. Default: 'value'
    - param2 (type|None): Description. Required.

  HTMX Integration: (if applicable)
    - Target: #element-id
    - Triggers: click, input
    - Swap: innerHTML, outerHTML
#}

{% from 'common/partials/dependency.html.jinja' import dependency %}

{% macro component_name(param1='default', param2=None) -%}
  <div class="{{ param1 }}">
    {# Implementation #}
  </div>
{%- endmacro %}
```

## Decision Tree

```mermaid
graph TD
    Start[Need UI Component] --> Q1{Exists 3+ times?}
    Q1 -->|No| Keep[Keep inline]
    Q1 -->|Yes| Q2{Single element?}

    Q2 -->|Yes| Atom[Create Atom<br/>common/partials/]
    Q2 -->|No| Q3{2-3 atoms combined?}

    Q3 -->|Yes| Q4{Domain-specific?}
    Q3 -->|No| Q5{Complex section?}

    Q4 -->|Yes| MoleculeD[Create Molecule<br/>{domain}/partials/]
    Q4 -->|No| MoleculeC[Create Molecule<br/>common/partials/]

    Q5 -->|Yes| Organism[Create Organism<br/>{domain}/partials/]
    Q5 -->|No| Template[Create Template<br/>{domain}/]
```

## File Structure

```text
templates/
  common/
    partials/
      file_source_icon.html.jinja  # ← Atom (reusable)
      icons.html.jinja
      tooltip.html.jinja

  data_management/
    files/
      partials/
        file_name_cell.html.jinja  # ← Molecule (domain)
        file_table_row.html.jinja  # ← Organism (domain)
        status_pill.html.jinja
      index.html.jinja             # ← Template/Page
```

## Refactoring Workflow

1. **Identify**: Find duplicate code (3+ times)
   ```bash
   grep -r "pattern" templates/
   ```

2. **Categorize**: Atom, Molecule, or Organism?
   - Atom: Single element (icon, button)
   - Molecule: 2-3 atoms (file + icon)
   - Organism: Complex section (table row)

3. **Extract**: Create new component file
   ```bash
   vim templates/common/partials/component_name.html.jinja
   ```

4. **Document**: Add docstring with usage

5. **Parameterize**: Add default parameters

6. **Update consumers**: Replace duplicates
   ```jinja
   {% from 'common/partials/component.html.jinja' import component %}
   {{ component(param='value') }}
   ```

7. **Test**: Visual + HTMX interactions

8. **Delete**: Remove old duplicate code

## Checklist

- [ ] Component has docstring
- [ ] Usage examples included
- [ ] Parameters with defaults
- [ ] Correct location (common vs domain)
- [ ] All consumers updated
- [ ] HTMX still works
- [ ] Old code deleted
- [ ] Visual regression passed

## Common Patterns

### Conditional Rendering

```jinja
{% macro status_badge(status) %}
  {% set styles = {
    'active': 'bg-green-100 text-green-800',
    'pending': 'bg-yellow-100 text-yellow-800'
  } %}
  <span class="badge {{ styles.get(status, 'bg-gray-100') }}">
    {{ status | title }}
  </span>
{% endmacro %}
```

### Size Variants

```jinja
{% macro icon(name, size='h-6 w-6') %}
  <span class="{{ size }}">
    <svg>...</svg>
  </span>
{% endmacro %}
```

### HTMX Target

```jinja
{% macro row(item) %}
  <tr id="item-{{ item.id }}" hx-swap="outerHTML">
    {# content #}
  </tr>
{% endmacro %}
```

## Anti-Patterns

❌ **Hard-coded values**

```jinja
{% macro icon() %}
  <span class="h-6 w-6 text-blue-500">...</span>
{% endmacro %}
```

✅ **Parameterized**

```jinja
{% macro icon(size='h-6 w-6', color='text-blue-500') %}
  <span class="{{ size }} {{ color }}">...</span>
{% endmacro %}
```

❌ **God component**

```jinja
{% macro everything(item, user, settings, permissions) %}
  {# 200 lines #}
{% endmacro %}
```

✅ **Focused components**

```jinja
{% macro icon(source) %}...{% endmacro %}
{% macro name(file) %}...{% endmacro %}
{% macro actions(file, user) %}...{% endmacro %}
```

## Resources

- Full Skill: `.github/skills/jinja2-atomic-design/SKILL.md`
- Example Atom: `templates/common/partials/file_source_icon.html.jinja`
- Example Organism: `templates/data_management/files/partials/file_table_row.html.jinja`
- Copilot Instructions: `.github/copilot-instructions.md` (Frontend Patterns section)
