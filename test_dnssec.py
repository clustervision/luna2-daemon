#!/usr/bin/env python3
"""
TRIX-1802: full matrix test for DNSSEC template rendering.
Tests the config.py mapping logic + actual template output for every scenario.
"""

from jinja2 import Environment, FileSystemLoader

TEMPLATE_PATH = 'daemon/templates'
PASS, FAIL = 0, 0


def map_cluster_to_vars(bind_legacy_db, dnssec_enable_db, dnssec_validation_db):
    """Replicates the mapping logic in utils/config.py dns_configure()."""
    bind_legacy = bool(bind_legacy_db)
    dnssec_enable = None
    dnssec_validation = None
    if bind_legacy and dnssec_enable_db is not None:
        dnssec_enable = 'yes' if dnssec_enable_db else 'no'
    if dnssec_validation_db is not None and dnssec_enable != 'no':
        dnssec_validation = 'yes' if dnssec_validation_db else 'no'
    return bind_legacy, dnssec_enable, dnssec_validation


def render(bind_legacy, dnssec_enable, dnssec_validation):
    env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
    env.autoescape = False
    tmpl = env.get_template('templ_dns_conf.cfg')
    out = tmpl.render(
        ALLOWED_QUERY=['any'],
        FORWARDERS=[],
        MANAGED_KEYS=None,
        OMAPIKEY=None,
        TSIGKEY=None,
        TSIGALGO=None,
        BIND_LEGACY=bind_legacy,
        DNSSEC_ENABLE=dnssec_enable,
        DNSSEC_VALIDATION=dnssec_validation,
    )
    return out


def check(label, bind_legacy_db, dnssec_enable_db, dnssec_validation_db,
          expect_enable=None, expect_validation=None):
    global PASS, FAIL
    bl, de, dv = map_cluster_to_vars(bind_legacy_db, dnssec_enable_db, dnssec_validation_db)
    out = render(bl, de, dv)

    results = []

    if expect_enable is None:
        ok = 'dnssec-enable' not in out
        results.append(('dnssec-enable absent', ok))
    else:
        ok = f'dnssec-enable {expect_enable};' in out
        results.append((f'dnssec-enable {expect_enable}', ok))

    if expect_validation is None:
        ok = 'dnssec-validation' not in out
        results.append(('dnssec-validation absent', ok))
    else:
        ok = f'dnssec-validation {expect_validation};' in out
        results.append((f'dnssec-validation {expect_validation}', ok))

    passed = all(r[1] for r in results)
    status = 'PASS' if passed else 'FAIL'
    if passed:
        PASS += 1
    else:
        FAIL += 1

    print(f"[{status}] {label}")
    if not passed:
        for name, ok in results:
            print(f"       {'ok' if ok else 'FAIL'}: {name}")
        print(f"       vars => bind_legacy={bl}, dnssec_enable={de}, dnssec_validation={dv}")


# --- full matrix ---

# modern BIND (bind_legacy=0), dnssec settings not configured
check("modern, no dnssec config",
      bind_legacy_db=0, dnssec_enable_db=None, dnssec_validation_db=None,
      expect_enable=None, expect_validation=None)

# modern BIND, validation on
check("modern, validation yes",
      bind_legacy_db=0, dnssec_enable_db=None, dnssec_validation_db=1,
      expect_enable=None, expect_validation='yes')

# modern BIND, validation off
check("modern, validation no",
      bind_legacy_db=0, dnssec_enable_db=None, dnssec_validation_db=0,
      expect_enable=None, expect_validation='no')

# modern BIND, dnssec_enable set but bind_legacy=0 — should be silently ignored
check("modern, dnssec_enable set (ignored)",
      bind_legacy_db=0, dnssec_enable_db=1, dnssec_validation_db=None,
      expect_enable=None, expect_validation=None)

# legacy BIND, DNSSEC fully off
check("legacy, dnssec-enable no",
      bind_legacy_db=1, dnssec_enable_db=0, dnssec_validation_db=None,
      expect_enable='no', expect_validation=None)

# legacy BIND, enable=no, validation=yes (validation must be suppressed)
check("legacy, dnssec-enable no + validation yes (suppressed)",
      bind_legacy_db=1, dnssec_enable_db=0, dnssec_validation_db=1,
      expect_enable='no', expect_validation=None)

# legacy BIND, enable=yes, no validation setting
check("legacy, dnssec-enable yes, no validation",
      bind_legacy_db=1, dnssec_enable_db=1, dnssec_validation_db=None,
      expect_enable='yes', expect_validation=None)

# legacy BIND, enable=yes, validation=yes
check("legacy, dnssec-enable yes + validation yes",
      bind_legacy_db=1, dnssec_enable_db=1, dnssec_validation_db=1,
      expect_enable='yes', expect_validation='yes')

# legacy BIND, enable=yes, validation=no
check("legacy, dnssec-enable yes + validation no",
      bind_legacy_db=1, dnssec_enable_db=1, dnssec_validation_db=0,
      expect_enable='yes', expect_validation='no')

# NULL bind_legacy (existing installs before migration) — should behave as modern
check("NULL bind_legacy (pre-migration), no dnssec config",
      bind_legacy_db=None, dnssec_enable_db=None, dnssec_validation_db=None,
      expect_enable=None, expect_validation=None)

check("NULL bind_legacy (pre-migration), validation yes",
      bind_legacy_db=None, dnssec_enable_db=None, dnssec_validation_db=1,
      expect_enable=None, expect_validation='yes')

print(f"\n{PASS + FAIL} tests: {PASS} passed, {FAIL} failed")
