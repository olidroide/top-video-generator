# Advanced Patterns for Atomic Design in Jinja2

**Companion Guide to SKILL.md**

This document contains real-world examples of advanced patterns discovered through production experience.

---

## Pattern 1: Context-Aware Navigation (with context)

**Problem:** Navigation menu needs `request.url` to highlight active section, but passing `request` through 5 component layers is tedious.

**Solution:** Use `with context` for top-level organisms that genuinely need global state.

```jinja
{# templates/common/partials/main_navigation.html.jinja #}
{#
  Organism: Main Navigation

  Uses `with context` because:
  - Needs request.url for active state
  - Needs current_user for permissions
  - Top-level component (not reused deeply)
#}

{% macro main_nav() %}
  <nav>
    <a href="/files" class="{% if '/files' in request.url.path %}active{% endif %}">
      Files
    </a>
    <a href="/conversations" class="{% if '/conversations' in request.url.path %}active{% endif %}">
      Conversations
    </a>
    {% if current_user.is_admin %}
      <a href="/admin" class="{% if '/admin' in request.url.path %}active{% endif %}">
        Admin
      </a>
    {% endif %}
  </nav>
{% endmacro %}

{# Usage in base layout #}
{% from 'common/partials/main_navigation.html.jinja' import main_nav with context %}
{{ main_nav() }}  {# No parameters needed #}
```

**When NOT to use:**
- Atoms (icons, buttons) → explicit parameters
- Reusable molecules → explicit parameters
- Deep nesting → refactor to avoid prop drilling

---

## Pattern 2: Multi-Variant Atoms (Design System)

**Problem:** Need button variants (primary, secondary, danger) without duplicating code.

**Solution:** Single atom with variant mapping.

```jinja
{# templates/common/partials/button.html.jinja #}
{% macro button(text, variant='primary', size='md', type='button', classes='', disabled=False, hx_attrs={}) -%}
  {# Variant class mapping #}
  {% set variant_classes = {
    'primary': 'bg-blue-600 hover:bg-blue-700 text-white',
    'secondary': 'bg-gray-200 hover:bg-gray-300 text-gray-800',
    'danger': 'bg-red-600 hover:bg-red-700 text-white',
    'ghost': 'bg-transparent hover:bg-gray-100 text-gray-800',
  } %}

  {# Size class mapping #}
  {% set size_classes = {
    'sm': 'px-3 py-1.5 text-sm',
    'md': 'px-4 py-2 text-base',
    'lg': 'px-6 py-3 text-lg',
  } %}

  <button
    type="{{ type }}"
    class="btn {{ variant_classes[variant] }} {{ size_classes[size] }} {{ classes }}"
    {% if disabled %}disabled{% endif %}
    {% for attr, value in hx_attrs.items() %}
      {{ attr }}="{{ value }}"
    {% endfor %}>
    {{ text }}
  </button>
{%- endmacro %}

{# Usage: Clean and declarative #}
{{ button('Save', variant='primary') }}
{{ button('Cancel', variant='ghost') }}
{{ button('Delete', variant='danger', hx_attrs={'hx-delete': '/files/123'}) }}
```

---

## Pattern 3: Slot Pattern (Flexible Composition)

**Problem:** Molecule needs flexible content (not just strings).

**Solution:** Use `caller()` for slot-like behavior.

```jinja
{# templates/common/partials/card.html.jinja #}
{% macro card(title='', footer='', classes='') -%}
  <div class="card {{ classes }}">
    {% if title %}
      <div class="card-header">
        <h3>{{ title }}</h3>
      </div>
    {% endif %}

    <div class="card-body">
      {{ caller() }}  {# Slot for content #}
    </div>

    {% if footer %}
      <div class="card-footer">
        {{ footer }}
      </div>
    {% endif %}
  </div>
{%- endmacro %}

{# Usage: Flexible content composition #}
{% call card(title='File Details', footer='Last updated: 2026-01-29') %}
  <p>File name: document.pdf</p>
  <p>Size: 2.5 MB</p>
  {{ file_source_icon(file.source.name) }}

  {# Complex nested content works #}
  <ul>
    {% for tag in file.tags %}
      <li>{{ tag }}</li>
    {% endfor %}
  </ul>
{% endcall %}
```

---

## Pattern 4: State Machine Components

**Problem:** Component appearance depends on complex state (loading, error, success, empty).

**Solution:** State enum with explicit rendering paths.

```jinja
{# templates/common/partials/async_content.html.jinja #}
{% macro async_content(state='loading', error_message='', empty_message='No data available') -%}
  {% if state == 'loading' %}
    <div class="flex items-center justify-center p-8">
      <svg class="animate-spin h-8 w-8 text-blue-600" ...>...</svg>
      <span class="ml-2">Loading...</span>
    </div>

  {% elif state == 'error' %}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
      <p class="text-red-800 font-semibold">Error</p>
      <p class="text-red-600">{{ error_message }}</p>
    </div>

  {% elif state == 'empty' %}
    <div class="bg-gray-50 rounded-lg p-8 text-center">
      <p class="text-gray-600">{{ empty_message }}</p>
    </div>

  {% elif state == 'success' %}
    {{ caller() }}  {# Render actual content #}

  {% endif %}
{%- endmacro %}

{# Usage: HTMX endpoint returns different states #}
<div hx-get="/files/list" hx-trigger="load" hx-target="this" hx-swap="innerHTML">
  {{ async_content(state='loading') }}
</div>

{# Backend returns appropriate state #}
# Success:
{% call async_content(state='success') %}
  {% for file in files %}
    {{ file_table_row(file, user) }}
  {% endfor %}
{% endcall %}

# Error:
{{ async_content(state='error', error_message='Failed to load files') }}

# Empty:
{{ async_content(state='empty', empty_message='No files uploaded yet') }}
```

---

## Pattern 5: HTMX Fragment with Multiple Targets

**Problem:** Single action updates multiple UI sections.

**Solution:** Use `jinja2-fragments` with multiple blocks + HTMX `hx-swap-oob`.

```jinja
{# templates/data_management/files/partials/file_actions.html.jinja #}

{% block status_pill %}
  <span id="status-{{ file.id }}" class="pill pill-{{ file.status }}">
    {{ file.status.to_display_string() }}
  </span>
{% endblock %}

{% block file_count %}
  <div id="file-count" class="badge">
    {{ total_files }} files
  </div>
{% endblock %}

{% block action_button %}
  <button
    id="approve-btn-{{ file.id }}"
    hx-put="/files/{{ file.id }}/approve"
    hx-target="#status-{{ file.id }}"
    hx-swap="outerHTML">
    Approve
  </button>
{% endblock %}
```

**Backend returns multiple fragments:**

```python
@router.put("/files/{file_id}/approve")
async def approve_file(file_id: str):
    file = await file_service.approve(file_id)
    total_files = await file_service.count_approved()

    # Return updated status pill + updated count with OOB swap
    return templates.TemplateResponse(
        "data_management/files/partials/file_actions.html.jinja",
        {
            "request": request,
            "file": file,
            "total_files": total_files,
        },
        # jinja2-fragments returns multiple blocks
        block_name=["status_pill", "file_count"],
    )
```

**HTML response:**

```html
<!-- Primary target (status pill) -->
<span id="status-123" class="pill pill-approved">Approved</span>

<!-- Out-of-band swap (file count in header) -->
<div id="file-count" class="badge" hx-swap-oob="true">
  42 files
</div>
```

---

## Pattern 6: Theme-Aware Components

**Problem:** Need dark mode / theming without duplicating components.

**Solution:** Use CSS variables + data attributes.

```jinja
{# templates/common/partials/themed_card.html.jinja #}
{% macro themed_card(title, theme='light') -%}
  <div class="card" data-theme="{{ theme }}">
    <h3 class="card-title">{{ title }}</h3>
    <div class="card-body">
      {{ caller() }}
    </div>
  </div>
{%- endmacro %}
```

**CSS (Tailwind config or custom):**

```css
.card[data-theme="light"] {
  @apply bg-white text-gray-900 border-gray-200;
}

.card[data-theme="dark"] {
  @apply bg-gray-800 text-gray-100 border-gray-700;
}

.card-title {
  @apply font-bold text-lg mb-2;
}

/* Or use CSS variables for flexibility */
.card {
  background: var(--card-bg, white);
  color: var(--card-text, black);
}
```

**Alternative: Tailwind dark mode classes:**

```jinja
{% macro themed_card(title) -%}
  <div class="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
    <h3>{{ title }}</h3>
    {{ caller() }}
  </div>
{%- endmacro %}
```

---

## Pattern 7: Progressive Enhancement (No JS Fallback)

**Problem:** HTMX requires JavaScript, but you want graceful degradation.

**Solution:** Use standard forms + HTMX progressive enhancement.

```jinja
{# templates/data_management/files/partials/upload_form.html.jinja #}
{% macro upload_form(action_url) -%}
  <form
    method="POST"
    action="{{ action_url }}"
    enctype="multipart/form-data"
    hx-post="{{ action_url }}"
    hx-target="#upload-status"
    hx-swap="innerHTML">

    <input type="file" name="file" required>

    <button type="submit" class="btn btn-primary">
      Upload
    </button>
  </form>

  <div id="upload-status" hx-target="this">
    {# HTMX replaces this on success/error #}
  </div>
{%- endmacro %}
```

**Behavior:**
- **With JS:** HTMX intercepts, uploads via AJAX, updates `#upload-status`
- **Without JS:** Standard form POST, full page reload with flash message

**Backend supports both:**

```python
@router.post("/files/upload")
async def upload_file(request: Request, file: UploadFile):
    result = await file_service.upload(file)

    # HTMX request: return fragment
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "common/partials/alert.html.jinja",
            {"message": "Upload successful", "type": "success"}
        )

    # Standard request: redirect with flash message
    request.session["flash"] = "Upload successful"
    return RedirectResponse("/files", status_code=303)
```

---

## Pattern 8: Pagination Organism

**Problem:** Need reusable pagination across multiple list views.

**Solution:** Create organism with prev/next/page numbers.

```jinja
{# templates/common/partials/pagination.html.jinja #}
{% macro pagination(current_page, total_pages, base_url, hx_target='#content') -%}
  {% if total_pages > 1 %}
    <nav class="flex items-center justify-between border-t border-gray-200 px-4 py-3">
      {# Previous button #}
      {% if current_page > 1 %}
        <a
          href="{{ base_url }}?page={{ current_page - 1 }}"
          hx-get="{{ base_url }}?page={{ current_page - 1 }}"
          hx-target="{{ hx_target }}"
          hx-swap="innerHTML"
          class="btn btn-ghost">
          Previous
        </a>
      {% else %}
        <span class="btn btn-ghost" disabled>Previous</span>
      {% endif %}

      {# Page numbers #}
      <div class="flex gap-1">
        {% for page in range(1, total_pages + 1) %}
          {% if page == current_page %}
            <span class="btn btn-primary">{{ page }}</span>
          {% else %}
            <a
              href="{{ base_url }}?page={{ page }}"
              hx-get="{{ base_url }}?page={{ page }}"
              hx-target="{{ hx_target }}"
              hx-swap="innerHTML"
              class="btn btn-ghost">
              {{ page }}
            </a>
          {% endif %}
        {% endfor %}
      </div>

      {# Next button #}
      {% if current_page < total_pages %}
        <a
          href="{{ base_url }}?page={{ current_page + 1 }}"
          hx-get="{{ base_url }}?page={{ current_page + 1 }}"
          hx-target="{{ hx_target }}"
          hx-swap="innerHTML"
          class="btn btn-ghost">
          Next
        </a>
      {% else %}
        <span class="btn btn-ghost" disabled>Next</span>
      {% endif %}
    </nav>
  {% endif %}
{%- endmacro %}
```

**Usage:**

```jinja
{# templates/data_management/files/index.html.jinja #}
<div id="content">
  {% for file in files %}
    {{ file_table_row(file, user) }}
  {% endfor %}
</div>

{{ pagination(
  current_page=page,
  total_pages=total_pages,
  base_url='/files',
  hx_target='#content'
) }}
```

---

## References

- [jinja2-fragments](https://pypi.org/project/jinja2-fragments/) - Block-level rendering
- [HTMX Out-of-Band Swaps](https://htmx.org/attributes/hx-swap-oob/) - Update multiple targets
- [Tailwind Dark Mode](https://tailwindcss.com/docs/dark-mode) - Theme support
- [Progressive Enhancement](https://developer.mozilla.org/en-US/docs/Glossary/Progressive_Enhancement)
