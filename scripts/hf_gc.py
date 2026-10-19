"""Free HF xet shared-store blobs (hub/blobs/xx/<hash>) whose referencing model dirs no longer exist.
Rotating a model with `rm -rf models--org--name` leaves its data in the shared store; run this afterwards."""
import os
import sys
import time

hub = os.path.join(sys.argv[1] if len(sys.argv) > 1 else os.environ["HF_HOME"], "hub")
os.chdir(hub)
now, freed = time.time(), 0
for root, _, files in os.walk("blobs"):
    for f in files:
        if f.endswith((".lock", ".refs", ".incomplete")):
            continue
        p = os.path.join(root, f)
        refs = open(p + ".refs").read().split() if os.path.exists(p + ".refs") else []
        if not refs or any(os.path.lexists(r) for r in refs) or now - os.stat(p).st_mtime < 900:
            continue
        freed += os.stat(p).st_size
        for x in (p, p + ".refs", p + ".lock"):
            if os.path.exists(x):
                os.remove(x)
print(f"hf_gc: freed {freed / 1e9:.1f} GB")
