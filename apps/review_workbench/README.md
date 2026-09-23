# Review workbench

Run from the repository root with `PYTHONPATH=src:. .venv/bin/python -m apps.review_workbench.app`.

- `app.py`: HTTP routes, request handling and the existing result/source entry points.
- `pages/`: page renderers for company research, source documents, datasets and query acceptance.
- `components/`: shared navigation, visual shell, report text and citation presentation.
- `data/`: document lookup and research archive import helpers.
- `static/css/`, `static/js/`: stylesheet and browser script sources. Python supplies escaped data and HTML; CSS and JavaScript are edited here.
- `assets.py`: fixed local asset lookup. Renderers still embed assets in returned HTML, preserving standalone pages and source-bridge behavior. This is not a public arbitrary-file endpoint.
- `workspace_check.py`: local workspace readiness checks.

Use canonical imports such as `apps.review_workbench.pages.query_runs`. The package retains old module aliases for existing consumers and monkeypatches; aliases refer to the same module object, not duplicated implementations.

Source bridge scripts use explicit JSON placeholders replaced by their Python callers. Preserve JSON escaping, source scope, and snapshot semantics when changing these inputs. Historical generated HTML and experiment snapshots are not rewritten by an asset edit.

This organization does not change layout, company lists, research states, model calls or adoption. Python still builds dynamic HTML; introducing a template engine or splitting the route handler is separate work.
