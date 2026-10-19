#!/bin/bash
# Kill hf downloads whose .incomplete files have not grown for 6 minutes; the run scripts' dl() retries them.
prev=-1; still=0
while true; do
  pgrep -f "[h]f download" >/dev/null || { prev=-1; still=0; sleep 60; continue; }
  cur=$(find /workspace -name "*.incomplete" -printf "%s\n" 2>/dev/null | awk '{s+=$1} END{print s+0}')
  if [ "$cur" = "$prev" ]; then still=$((still+1)); else still=0; fi
  prev=$cur
  if [ $still -ge 6 ]; then echo "$(date +%T) stalled at $cur bytes; restarting downloads"; pkill -f "[p]ython.*hf download"; still=0; fi
  sleep 60
done
