# JavaScript / Pyodide checks

These run in Node (no browser needed) and test the code that runs in the student's browser.

```
node tests_js/test_speaking.js                     # speaking assessment script (stubbed page)
node tests_js/test_notifications.js                # browser-notification script (stubbed page)

# The two checks below need Pyodide for Node (install once, in any folder):
npm install pyodide@0.26.4
python manage.py export_problems > problems.json
PYODIDE_PKG=./node_modules/pyodide node tests_js/test_pyodide_problems.js problems.json   # every problem inside Pyodide
PYODIDE_PKG=./node_modules/pyodide node tests_js/test_coding_flow.js problems.json        # coding.js + worker + Pyodide, end to end
```
