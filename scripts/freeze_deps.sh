#!/usr/bin/env sh
# Run on the DEPLOYMENT machine after `pip install -r requirements.txt` and after verify_opencv5.py passes.
# Produces requirements.lock.txt with exact versions: commit it before you tag the release.
set -e
python scripts/verify_opencv5.py
pip freeze | grep -iE '^(opencv|numpy|scikit-image|scipy|flask|werkzeug|gunicorn|boto3|pyjwt|cryptography|imageio|networkx|pillow|tifffile|lazy)' > requirements.lock.txt
echo "wrote requirements.lock.txt"; cat requirements.lock.txt
