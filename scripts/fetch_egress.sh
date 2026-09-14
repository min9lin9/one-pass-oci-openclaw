#!/usr/bin/env bash
set -euo pipefail
# Restricted reader UID only, NOT all OpenClaw networking.
# Configure while the reader is quiescent. The service marker is not proof that
# another administrator has not subsequently changed the firewall.
uid=$(id -u clawfetch)
rm -f /run/oracle-fetch-egress.ready
for ipt in iptables ip6tables; do
  chain="OAS_F_$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
  "$ipt" -w -N "$chain"
  mapfile -t resolvers < <(/usr/bin/python3 - "$ipt" <<'PY'
import ipaddress,pathlib,sys
family=4 if sys.argv[1]=='iptables' else 6
for line in pathlib.Path('/etc/resolv.conf').read_text().splitlines():
    fields=line.split()
    if len(fields)>1 and fields[0]=='nameserver':
        try: value=ipaddress.ip_address(fields[1])
        except ValueError: continue
        if value.version==family: print(value)
PY
)
  # Only an explicit configured DNS resolver can use the private-address exception.
  for resolver in "${resolvers[@]}"; do
    "$ipt" -w -A "$chain" -d "$resolver" -p udp --dport 53 -j RETURN
    "$ipt" -w -A "$chain" -d "$resolver" -p tcp --dport 53 -j RETURN
  done
  if [[ "$ipt" == iptables ]]; then
    ranges=(0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 192.0.0.0/24 198.18.0.0/15 224.0.0.0/4 240.0.0.0/4)
  else
    ranges=(::/128 ::1/128 ::ffff:0:0/96 64:ff9b::/96 64:ff9b:1::/48 2002::/16 fc00::/7 fe80::/10 ff00::/8)
  fi
  for net in "${ranges[@]}"; do "$ipt" -w -A "$chain" -d "$net" -j REJECT; done
  "$ipt" -w -A "$chain" -j RETURN
  # Build off-path first; insert one complete policy before removing old ones.
  "$ipt" -w -I OUTPUT 1 -m owner --uid-owner "$uid" -j "$chain"
  mapfile -t old_chains < <("$ipt" -S OUTPUT | /usr/bin/python3 -c '
import shlex,sys
uid,current=sys.argv[1:]
seen=set()
for line in sys.stdin:
    row=shlex.split(line)
    if "--uid-owner" not in row or "-j" not in row: continue
    owner=row[row.index("--uid-owner")+1];target=row[row.index("-j")+1]
    if owner==uid and target!=current and (target=="OAS_FETCH" or target.startswith("OAS_F_")):
        if target not in seen:print(target);seen.add(target)
' "$uid" "$chain")
  for old in "${old_chains[@]}"; do
    while "$ipt" -w -C OUTPUT -m owner --uid-owner "$uid" -j "$old" 2>/dev/null; do
      "$ipt" -w -D OUTPUT -m owner --uid-owner "$uid" -j "$old"
    done
    "$ipt" -w -F "$old"
    "$ipt" -w -X "$old"
  done

done
install -m 644 /dev/null /run/oracle-fetch-egress.ready
