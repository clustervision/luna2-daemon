# luna2-daemon test suite

Unit and regression tests for the daemon. The suite imports the **real** daemon
code (`utils.*`, `common.*`) — nothing is duplicated inline — and runs without a
live `/trinity` deployment or an MSSQL database.

## Layout

```
tests/
  conftest.py            bootstrap + shared fixtures (see "How it works")
  requirements-test.txt  dev-only deps (pytest); not shipped with the daemon
  cases/
    helper_cases.py      data-driven cases for Helper methods
    validate_cases.py    data-driven cases for validate_input functions
    config_cases.py      data-driven cases for Config (pure methods)
  unit/
    test_config.py       runs config_cases.py
    test_helper.py       runs helper_cases.py + hand-written edge tests
    test_validate_input.py
  regression/
    test_helper_golden.py    network math pinned to a stored golden file
    test_database_sqlite.py  real CRUD against a temp SQLite database
    golden/network_math.json the golden baseline
    regen_network_math.py    regenerate the golden after an intended change
```

## Running

```bash
pip install -r tests/requirements-test.txt    # one-time
pytest                                         # from the repo root
pytest tests/unit                              # unit tests only
pytest -m regression                           # regression tests only
pytest -m "not regression"                     # everything except regression
pytest -k make_bool                            # a single case by name
```

## How it works

The daemon's `common/constant.py` reads `/trinity/local/luna/daemon/config/luna.ini`
and a key file **at import time** and aborts if they are missing. `tests/conftest.py`
injects a minimal stand-in `common.constant` into `sys.modules` before any daemon
module is imported, so the genuine code imports and runs unchanged. `pytest.ini`
puts `daemon/` and `tests/` on the path.

Key fixtures (in `conftest.py`):

- `helper` — a `Helper()` instance.
- `config` — a `Config()` instance.
- `constant` — the stubbed `CONSTANT` dict, if a test needs to read or tweak config.
- `sqlite_db_path` — an empty temp SQLite database wired into config (no schema); for
  tests that build tables themselves.
- `sqlite_db` — as `sqlite_db_path` but with the full schema built from the daemon's
  own `database_layout` definitions; the data layer runs against it for real.

## Adding tests

### The quick way: add a case to a table (no test code)

Most functions take inputs and return a value. To cover one, append a dict to the
relevant table — the parametrized test picks it up automatically.

**Helper methods** → edit `cases/helper_cases.py`. Reference the method by name:

```python
{"id": "get_netmask-8", "func": "get_netmask", "args": ["10.0.0.0/8"],
 "expected": "255.0.0.0"},
```

**validate_input functions** → edit `cases/validate_cases.py`. Reference the
callable directly (these are module-level functions, not methods):

```python
from common.validate_input import filter_data
{"id": "filter-keeps-digits", "func": filter_data, "args": ["abc123"],
 "expected": "abc123"},
```

Case dict fields:

| field      | required | meaning                                                   |
|------------|----------|-----------------------------------------------------------|
| `id`       | yes      | unique label shown in the test report                     |
| `func`     | yes      | Helper method **name** (helper table) or the **callable** (validate table) |
| `args`     | no       | list of positional args (default `[]`)                    |
| `kwargs`   | no       | dict of keyword args (default `{}`)                       |
| `expected` | yes\*    | the value the call must return                            |
| `raises`   | no       | an exception type the call must raise (use instead of `expected`) |

\* exactly one of `expected` or `raises`.

Use the table only for functions whose result depends purely on their inputs.
Anything needing a database, filesystem, or other setup goes in a dedicated test
module with the right fixture (see `regression/test_database_sqlite.py`).

### The full way: write a test function

For behaviour a value table can't express — non-deterministic output, in-place
mutation, stateful objects, multi-step flows — add a normal test to the matching
`test_*.py`, requesting fixtures as needed:

```python
def test_encrypt_is_reversible(helper):
    token = helper.encrypt_string("secret")
    assert helper.decrypt_string(token) == "secret"
```

## Regression / golden tests

`test_helper_golden.py` pins the network-math helpers to `golden/network_math.json`.
If you intentionally change that behaviour, regenerate and review the diff before
committing:

```bash
python tests/regression/regen_network_math.py
git diff tests/regression/golden/network_math.json
```

An **unexpected** diff means a behavioural regression — investigate, don't just
regenerate.
