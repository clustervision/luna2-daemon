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


# luna controller zero-touch provisioning (ZTP) for NVIDIA NVOS / NVLink switches

Luna can hand an NVOS switch its DHCP boot options and serve the ZTP recipe it
fetches, so the switch installs NVOS and applies its config on first boot.

- place the NVOS image in luna's files directory, `/trinity/local/luna/files`. It is
  then served at `GET /files/<image>` with **no token**, which the switch needs since
  it has no credentials during ZTP. Keep a `.bin` extension: luna only token-gates the
  image extensions `.gz/.tar/.bz/.bz2/.torrent` (see `daemon/base/file.py`), so a
  `.bin` NVOS image downloads token-free.
- a switch record carries four ZTP fields (auto-migrated onto existing databases):
  - `default_url` — DHCP option 114; the NVOS/ONIE image URL, reused as the ZTP
    `01-image` install URL. Point it at the `/files` URL above.
  - `bootfile` — DHCP option 67 (`filename`); the URL the switch fetches its ZTP
    recipe from, normally luna's own `/boot/switch/<name>` endpoint
  - `next_server` — optional `next-server` for TFTP-based setups
  - `ztpconfig` — the NVOS commands-list applied by ZTP; when empty luna serves a
    minimal generated default (hostname + ssh) instead
- set them on the switch (these reservation fields render into both the ISC and
  Kea DHCP configs):
```
luna switch change --default-url http://<controller>:7050/files/<nvos>.bin \
                   --bootfile http://<controller>:7050/boot/switch/<name> \
                   <name>
```
  > Note: the matching `luna switch` flags are a separate addition in luna2-cli;
  > until they land the fields are set through the REST API (`config/switch/<name>`).
- luna then serves, for a switch `<name>`:
  - `GET /boot/switch/<name>` — the ZTP recipe JSON (`01-image` → `02-commands-list`
    → `03-connectivity-check`)
  - `GET /boot/switch/<name>/commands` — the commands-list applied by `02-commands-list`
- boot the switch; it requests DHCP, receives option 114/67, fetches the recipe and
  provisions itself


