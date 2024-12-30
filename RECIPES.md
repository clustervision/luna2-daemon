# luna controller using dhcp-relay on another subnet

- the controller needs a network wherein it resides. This could be any network, for now we use ctrl-network after renaming the default cluster network:
```
luna network rename cluster ctrl-network
```
- stop dhcp on the ctrl-network:
```
luna network change -dhcp n ctrl-network
```
- create a new network for the remote nodes:
```
luna network add -N <network ip>/<cidr> -dhcp y -ds <dhcp range start> -de <dhcp range end> -g <gateway/ip of router> -gm 10 cluster
```
- configure the provision interface of e.g. compute group to be in the new network:
```
luna group change -if BOOTIF -N cluster compute
```
- boot the nodes


# luna controller to automatically boot nodes, use the mac address as node name base, while using a dhcp pool

- make sure that bind is the owner/has write access for the files in /var/named/<zone>*
```
chown named.named /var/named/*
```
- assuming that the cluster network has already enabled dhcp, set the dhcp_nodes_in_pool:
```
luna network change -dnip y cluster
```
- make sure there is only one group, e.g. compute, and have this group set the provisioning interface to dhcp
```
luna group change -if BOOTIF -dhcp y compute
```
- enable the use of mac address as host name base while ensuring automatic node name detection:
```
luna cluster change -m y -o y -nx y
```
- boot the nodes


