# luna controller using dhcp-relay on another subnet

- the controller needs a network wherein it resides. This could be any network, for now we use ctrl-network after renaming the default cluster network:
```
luna network rename cluster ctrl-network
```
- stop dhcp on the ctrl-network:
```
luna network change --dhcp n ctrl-network
```
- create a new network for the remote nodes:
```
luna network add -N <network ip>/<cidr> --dhcp y --ds <dhcp range start> --de <dhcp range end> --gw <gateway/ip of router> --gm 10 cluster
```
- configure the provision interface of e.g. compute group to be in the new network:
```
luna group change --if BOOTIF -N cluster compute
```
- boot the nodes


# luna controller to automatically boot nodes, use the mac address as node name base, while using a dhcp pool

- make sure that bind is the owner/has write access for the files in /var/named/<zone>*
```
chown named.named /var/named/*
```
- assuming that the cluster network has already enabled dhcp, set the dhcp_nodes_in_pool:
```
luna network change --dnip y cluster
```
- make sure there is only one group, e.g. compute, and have this group set the provisioning interface to dhcp
```
luna group change --if BOOTIF -dhcp y compute
```
- enable the use of mac address as host name base while ensuring automatic node name detection:
```
luna cluster change --cm y --co y --nx y
```
- boot the nodes


# luna controller zero-touch provisioning (ZTP) for switches

Luna can hand a switch its DHCP boot options and serve the ZTP recipe it
fetches, so the switch installs its image and applies its config on first boot.

- place the switch image in luna's files directory, `/trinity/local/luna/files`. It is
  then served at `GET /files/<image>` with **no token**, which the switch needs since
  it has no credentials during ZTP. Keep a `.bin` extension: luna only token-gates the
  image extensions `.gz/.tar/.bz/.bz2/.torrent` (see `daemon/base/file.py`), so a
  `.bin` image downloads token-free.
- a switch record carries these ZTP fields (auto-migrated onto existing databases):
  - `netboot` — master toggle, **off by default** (unset counts as off). Set it on to
    render the boot options below into the DHCP reservation; off keeps the IP reservation
    but emits no `default-url`/`filename`/`next-server`, so the switch does not fetch the
    image or re-run ZTP. Leave it off once a switch is provisioned to lock it against
    reinstall. If netboot is on but **neither `default_url` nor `bootfile` is defined**,
    luna logs a warning and skips netboot for that switch (no half-configured reservation).
  - `default_url` — DHCP option 114; a **controller-relative path** to the switch
    image (e.g. `files/<image>.bin`), reused as the ZTP `01-image` install URL.
  - `bootfile` — DHCP option 67 (`filename`); a **controller-relative path** to the ZTP
    recipe, normally luna's own `boot/switch/<name>` endpoint.
  - `ztpconfig` — the switch config applied by ZTP; when empty luna serves a
    minimal generated default (hostname + ssh) instead.
  - `ztpformat` — `commands` (default) or `yaml`. With `yaml` (and a `ztpconfig`
    present) luna emits the ZTP recipe's config section as `02-startup-file` (declarative) instead of `02-commands-list`; the served content is unchanged. ZTP
    itself downloads the section URL, so the same `/boot/switch/<name>/commands`
    endpoint serves either format.
- `default_url`/`bootfile` store only the path: luna prepends the controller
  `http://<nextserver>:<nextport>/` automatically, reusing the same per-reservation
  `nextserver`/`nextport` the node `filename` already uses. The `next-server` line is
  the controller too (no separate field). Set them on the switch (rendered into both the
  ISC and Kea DHCP configs):
```
luna switch change --netboot y \
                   --default-url files/<image>.bin \
                   --bootfile boot/switch/<name> \
                   <name>
```
- luna then serves, for a switch `<name>`:
  - `GET /boot/switch/<name>` — the ZTP recipe JSON (`01-image` → `02-commands-list`
    or `02-startup-file` → `03-connectivity-check`)
  - `GET /boot/switch/<name>/commands` — the `ztpconfig` (commands-list or declarative yaml)
- boot the switch; it requests DHCP, receives option 114/67, fetches the recipe and
  provisions itself
- **Security caveat:** these `/boot/switch/<name>` endpoints are **unauthenticated** (the
  switch has no token during ZTP, same as the node `/boot` routes), so the served
  `ztpconfig` is readable by anyone who can reach the controller on that port and knows or
  guesses a switch name. Keep `ztpconfig` to identity/services only — do **not** put
  passwords, hashes or other secrets in it.


