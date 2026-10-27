# luna2-daemon

The Luna 2 daemon is the central service of Luna, the provisioning and cluster
management system of TrinityX. It runs on every controller, keeps the cluster
configuration in its database, provisions nodes and switches over the network and exposes
all of it through a REST API. The `luna` command-line tool (luna2-cli), the node-side
client (luna2-client) and the Luna utilities (luna2-utils) all talk to this API.

The design of the daemon — its layering, plugins and replication — is described on the
[Luna daemon architecture](https://docs.clustervision.com/admin/luna-daemon-architecture/)
page.

## Features

### Cluster configuration
- One source of truth for the cluster: networks, groups, nodes, OS images, switches,
  other devices, racks, BMC and Redfish setups, OS users and static routes.
- Group-level defaults with node-level overrides: a node inherits from its group
  unless it sets a value itself.
- Dual-stack networking: IPv4 and IPv6 addressing, next free IP lookup and per-network
  DNS records.
- Export and import of the complete cluster configuration.

### Network provisioning
- Network boot of nodes through iPXE, with provisioning over HTTP or BitTorrent (the
  daemon runs its own tracker), and kickstart installs.
- Diskless and diskful nodes, disk layouts and RAID via boot scripts.
- Node detection by MAC address, by switch port or from a cloud provider, and manual
  assignment of a MAC address to a node or group.
- Switch zero-touch provisioning (ZTP) and switch boot configuration.
- Network configuration rendered per operating system: Red Hat Enterprise Linux 8, 9 and
  10 and compatibles, Ubuntu and openSUSE, including bonds.
- DHCP (Kea or ISC dhcpd, IPv4 and IPv6, with relay support) and DNS (BIND) generated
  from the configuration.
- Network mounts (NFS and others) defined at cluster, group or node level and rendered
  into the node's fstab.

### OS images
- OS image management: packing, cloning, tagging, kernel selection and certificate
  updates.
- `osgrab` and `ospush`: capture a running node's filesystem into an image, or push an
  image onto running nodes.

### Hardware management
- Power control and status (on, off, reset, cycle) through IPMI or Redfish, per node or
  in bulk.
- BMC and Redfish setup at provisioning time, including Redfish account provisioning.
- One-time next-boot override.
- BIOS configuration profiles: grab from a node, push to a node or group, track status.
- Firmware catalogue: preview and push firmware updates to nodes or groups, track status.
- Node hardware inventory, collected in-band and over Redfish.
- Vendor-specific behaviour through plugins (Dell, HPE, Lenovo, IBM, Gigabyte and a
  generic default).

### Secrets and profiles
- Secrets at cluster, group and node level, stored encrypted and delivered to the node
  they belong to.
- Profiles: sets of files assigned to groups or nodes and applied on the node, with
  delivery status per node.

### Access control (RBAC)
- Role-based access control (RBAC) on every configuration object, modelled on POSIX
  permissions: each object has owners, user groups and an access mode, changed with
  `chmod`, `chgrp` and `chown`.
- Users and user groups, with authentication against local accounts, PAM or LDAP,
  tried in a configurable order.
- Objects outside a user's scope are not visible to that user at all.
- Token-based API authentication; node tokens are scoped to the node they belong to,
  with optional TPM-based node authentication.

### High availability
- Controller high availability: master election, controller state and an overrule
  switch.
- A journal replicates every configuration change to the other controllers.
- OS images are synchronised between controllers and verified by hash.

### Monitoring and integration
- Node, queue, service, HA, image and synchronisation status through the monitor API.
- Control of the DHCP and DNS services through the API.
- Export and import plugins, including Prometheus targets and alerting rules.
- Hooks that run custom code on configuration, control and monitoring events.

## Functions

All routes are served under the daemon's API endpoint. Requests and responses are JSON.
Long-running actions return a request id whose progress can be followed on a status route.

| Area | Routes | What it does |
|---|---|---|
| Authentication | `/token`, `/whoami`, `/tpm/<node>`, `/filesauth` | Log in and obtain a token; show the caller's identity; node authentication |
| Cluster | `/config/cluster`, `/config/cluster/mounts`, `/config/cluster/export`, `/config/cluster/import` | Cluster settings, cluster-wide mounts, full configuration export and import |
| Networks | `/config/network/<name>`, `…/_nextfreeip`, `…/_member`, `/config/dns/<name>` | Networks, address lookup, members and additional DNS records |
| Groups | `/config/group/<name>`, `…/interfaces`, `…/mounts`, `…/profiles`, `…/disklayout`, `…/_ospush` | Groups, their interfaces, mounts, profiles and disk layout |
| Nodes | `/config/node/<name>`, `…/interfaces`, `…/mounts`, `…/profiles`, `…/disklayout`, `…/_osgrab`, `…/_ospush` | Nodes, their interfaces, mounts, profiles and disk layout; grab or push an OS |
| OS images | `/config/osimage/<name>`, `…/_pack`, `…/_cancel`, `…/_updatecerts`, `…/kernel`, `…/tag`, `/config/osimagetag` | OS images, packing, kernels and tags |
| Switches and devices | `/config/switch/<name>`, `/config/otherdev/<name>`, `/config/rack/<name>`, `/config/rack/inventory` | Switches and their ports, other devices, racks and rack placement |
| BMC and Redfish | `/config/bmcsetup/<name>`, `/config/redfishsetup/<name>`, `/config/node/redfishaccounts/_provision` | BMC and Redfish setups; Redfish account provisioning |
| BIOS | `/config/biosconfig/<name>`, `/config/node/<name>/_biosgrab`, `…/_biospush`, `/config/biosconfig/status` | BIOS profiles, grab and push, status |
| Firmware | `/config/firmwarecatalog/<name>`, `…/firmware/_preview`, `…/_firmwarepush`, `/config/firmwarecatalog/status` | Firmware catalogue, preview, push and status |
| Inventory | `/config/node/inventory`, `/config/node/<name>/inventory`, `…/inventory/_redfish` | Node hardware inventory |
| Routes | `/config/route/<name>`, `…/_couple`, `…/_decouple` | Static routes and their assignment to networks, groups and nodes |
| Secrets | `/config/secrets/cluster`, `/config/secrets/group/<name>`, `/config/secrets/node/<name>` | Secrets per level |
| Profiles | `/config/profiles/<name>`, `/config/profiles/status`, `/config/profiles/node/<name>` | Profiles, their files and delivery status |
| OS users | `/config/osuser/<name>`, `/config/osgroup/<name>` | Operating system users and groups |
| Cloud | `/config/cloud/<name>` | Cloud definitions |
| Access control (RBAC) | `/config/user/<name>`, `/config/usergroup/<name>`, `…/members`, `/config/usergroupmap`, `/config/<entity>/<name>/_chmod`, `…/_chgrp`, `…/_chown` | Users, user groups, external group mapping and per-object permissions |
| Status | `/config/status/<request_id>`, `/control/status/<request_id>`, `/service/status/<request_id>` | Progress of long-running requests |
| Control | `/control/action/<subsystem>/<host>/_<action>`, `/control/action/<subsystem>/_<action>` | Power, Redfish and next-boot actions, per node or in bulk |
| Services | `/service/<name>/<action>` | Start, stop, restart, reload and status of the DHCP and DNS services |
| Boot | `/boot`, `/boot/search/mac/<mac>`, `/boot/manual/…`, `/boot/install/<node>`, `/kickstart/install/<node>`, `/boot/switch/<name>`, `/boot/scripts/<script>`, `/boot/roles/<role>`, `/boot/profiles/<profile>` | Everything a node or switch fetches while it boots and installs |
| Files | `/files`, `/files/<file>`, `/announce`, `/scrape` | Image and file download, BitTorrent tracker |
| High availability | `/ping`, `/ha/state`, `/ha/master`, `/ha/controllers`, `/ha/overrule/_set` | Controller state and master election |
| Journal | `/journal`, `/journal/<name>` | Replication of changes between controllers |
| Monitoring | `/monitor/status`, `/monitor/node/<node>`, `/monitor/queue`, `/monitor/service/<name>`, `/monitor/ha`, `/monitor/sync`, `/monitor/osimage`, `/monitor/mother` | Node, queue, service, HA and synchronisation status |
| Hashes and tables | `/hash/…`, `/table/hashes`, `/table/data/<name>` | Configuration and file hashes and table data, used for HA consistency |
| Plugins | `/export/<name>`, `/import/<name>` | Export and import through plugins |

Objects are changed with `POST` on their route. Most objects also have `_clone` and
`_delete` actions, and `_member` lists the objects that use them.

## Plugins

Site-, OS- and vendor-specific behaviour lives in plugins under `daemon/plugins/`, not in the
daemon core:

| Directory | Purpose |
|---|---|
| `auth/` | Authentication sources: local, PAM, LDAP |
| `boot/bmc/` | BMC configuration per vendor |
| `boot/detection/` | Node detection by switch port or cloud |
| `boot/network/` | Network configuration per operating system |
| `boot/provision/` | Provisioning method: HTTP, BitTorrent, kickstart |
| `boot/roles/`, `boot/scripts/` | Boot roles and scripts, such as bonding, diskful installs and RAID |
| `control/` | Power control: IPMI (default) and Redfish |
| `redfish/` | Redfish vendor differences |
| `osimage/` | Image packing, `osgrab` and `ospush` operations |
| `osuser/` | OS user management |
| `profile/` | Profile delivery to nodes |
| `export/`, `import/` | Export and import formats, such as Prometheus |
| `hooks/` | Custom code run on configuration, control and monitoring events |

## Configuration

The daemon reads two files from `daemon/config/`. The copies in this repository are
examples.

### luna.ini

`luna.ini` holds the daemon's settings and is read at every start. Its sections:

| Section | Settings |
|---|---|
| `[LOGGER]` | Log level and log file |
| `[API]` | API endpoint and protocol, the built-in API account, token secret and token expiry, certificate verification |
| `[DATABASE]` | Database driver (SQLite3 by default, other databases through ODBC), database location and credentials |
| `[FILES]` | Image directory, image file store, temporary directory, maximum packing time |
| `[SECRETS]` | Key used to encrypt stored secrets |
| `[WEBSERVER]` | Port and protocol of the web server that serves images and files |
| `[SERVICES]` | DHCP and DNS service names and how they are controlled |
| `[DHCP]` | OMAPI key for ISC dhcpd |
| `[BMCCONTROL]` | Batch size and delay for bulk BMC actions |
| `[TEMPLATES]` | Template directory and template list |
| `[PLUGINS]` | Plugin directory, image filesystem plugin, allowed export and import plugins |
| `[AUTH]` | Order of the authentication sources, for example `local, pam` |
| `[AUDIT]` | Location of the audit trail log file |

**On a TrinityX cluster, the TrinityX installer writes a fresh `luna.ini` on every run and
replaces whatever the file contained.** Change settings through the TrinityX configuration,
not in the file on the controller, or the next installer run removes them. The daemon does
not depend on TrinityX: it also runs on its own, and `luna.ini` is then maintained by hand.

### bootstrap.ini

`bootstrap.ini` holds the initial cluster: DNS search domains and forwarders, the controllers,
the networks, and the default group, OS image and BMC setup. The daemon reads it only when it
starts with an empty database, creates the cluster from it and renames it to
`bootstrap-<timestamp>.ini`. After that the database is the source of truth, and changing
`bootstrap.ini` has no effect on an existing cluster. On a TrinityX cluster the installer
writes this file.

---

Luna 2 Daemon is a part of the Luna 2 Project.
Luna 2 Daemon is a daemon with Microservices(REST API).
It will use TCP/IP connectivity port 7050 as the default.

## Installation

Luna is part of TrinityX, and also works on its own. As part of TrinityX, the
daemon is tested on Red Hat Enterprise Linux, Rocky Linux and AlmaLinux 8, 9 and 10, and on
CentOS Stream 9.

The daemon needs:

- Python 3.10. Any Python 3.10 will do, including one you build yourself.
- The `luna2-daemon` package installed in that Python with pip. Build it from this
  repository (`pip wheel .`), or take it from the TrinityX package repository; it is not on
  PyPI.
- The daemon at `/trinity/local/luna/daemon`; this path is fixed in the code.
- A `luna.ini`, and a `bootstrap.ini` for the first start (see Configuration above).
- A service that runs `gunicorn --config /trinity/local/luna/daemon/config/gunicorn.py luna:daemon`
  from that directory. It listens on port 7050, IPv4 and IPv6.

With the default SQLite3 database no database server or ODBC driver is needed. The daemon
logs to the file set in `luna.ini`, by default `/var/log/luna/luna2-daemon.log`.

On a TrinityX controller the TrinityX installer provides all of this: its own Python 3.10 in
`/trinity/local/python` (the `luna2-python` package), the `luna2-daemon` pip package linked
to `/trinity/local/luna/daemon`, both configuration files, and the `luna2-daemon` systemd
service.

## Contributing

Please read the [contribution guidelines](Guidelines.rst) before submitting changes, including the legal terms that apply to all contributions.
