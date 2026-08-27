# Redfish emulator harness

`tests/unit/test_bios_against_emulator.py` talks to a real Redfish service over
HTTP instead of to a fake we wrote. This is what starts one.

```sh
python3 -m venv ~/sushy-emu-venv
~/sushy-emu-venv/bin/pip install sushy-tools
~/sushy-emu-venv/bin/python tests/emulator/launch.py
```

Then `pytest tests/unit/test_bios_against_emulator.py`. Without a reachable
emulator those tests skip, so the default suite stays hermetic and needs nothing
installed.

`LUNA_REDFISH_EMULATOR=host:port` points the tests at a different one — a real
BMC works too, though the write tests will change that machine's BIOS, so do not
aim them at anything you care about.

## What this is for, and what it is not for

It exercises the **plumbing**: our client against somebody else's reading of the
specification. Routes, the `@Redfish.Settings` annotation, the settings object
pointer, JSON shapes, error bodies and status codes are all sushy-tools' — so a
misconception of ours about how Redfish behaves shows up here, where against our
own fake it cannot.

It does **not** test the feature. sushy-tools models no pending area: its BIOS
PATCH route writes into the same store its BIOS GET route reads, so a write lands
with no reset. Staging is the whole point of a staged apply, so the fake BMC in
`tests/unit/test_bios_push.py` — which stages, applies on reset, and can silently
drop an attribute — remains the test of the behaviour. The two are complementary
and neither is redundant.

## Why a driver of ours is in here

sushy-tools implements BIOS only in its libvirt driver, and the emulator's own
fake driver has no BIOS at all. `biosdriver.py` adds the three calls the BIOS
routes need — get, set, reset — and nothing else. The attribute *store* is
therefore ours; every byte that goes over the wire is still sushy-tools'.
