# Redfish emulator harness

`tests/unit/test_bios_against_emulator.py` talks to a real Redfish service over
HTTP instead of to a fake we wrote. This is what starts one.

```sh
python3 -m venv ~/sushy-emu-venv
~/sushy-emu-venv/bin/pip install 'sushy-tools @ git+https://opendev.org/openstack/sushy-tools'
~/sushy-emu-venv/bin/python tests/emulator/launch.py
```

Then `pytest tests/unit/test_bios_against_emulator.py`. Without a reachable
emulator those tests skip, so the default suite stays hermetic and needs nothing
installed.

`LUNA_REDFISH_EMULATOR=host:port` points the tests at a different one. A real BMC
works too — but the write tests change that machine's BIOS and reset it, so do
not aim them at anything you care about.

## From source, not from PyPI, for now

Staged BIOS — a PATCH landing in a pending area and being applied on reset — is
implemented on sushy-tools' master and is **not in 2.2.0**, the newest release at
the time of writing. Installing from PyPI gets an emulator that applies BIOS
writes immediately, and the staging tests here will fail against it rather than
skip, which is the correct outcome: they are asserting behaviour the service is
supposed to have.

Once a release past 2.2.0 exists, this can go back to a plain `pip install
sushy-tools` and this section can go.

## What this is for

It exercises our client against an implementation we did not write. Routes, the
`@Redfish.Settings` annotation, the settings object, the pending area, the
apply-on-reset, JSON shapes, error bodies and status codes are all sushy-tools' —
so a misconception of ours about how Redfish behaves shows up here, where against
our own fake it cannot.

Two things it has already caught, neither of which a fixture of ours would have:

- **A registry named in one field and published under another.** This service's
  BIOS resource names `BiosAttributeRegistryP89.v1_0_0`, its collection entry
  calls the same registry `BiosAttributeRegistry.v1_0_0` / `BiosAttributeRegistry1.0`,
  and only the registry document itself agrees with the BIOS resource. We matched
  one field and refused; sushy, the reference client, indexes all of them and
  resolves it. Ours was the bug.
- **A `GracefulRestart` preference**, which neither real machine we have access to
  offers at all, so the ordering in `RESET_ORDER` is only exercised here.

## What it does not replace

`tests/unit/test_bios_push.py` and its fake BMC. The emulator stages and applies
on reset, which is most of what the fake is for — but the fake can also **silently
drop** an attribute it accepted, which is the failure `MAX_ATTEMPTS` exists for and
the one nobody predicts. No emulator models a board quietly ignoring you. Nor does
either of them replace hardware: only a real board shows what a real board does.
