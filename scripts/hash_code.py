"""Make the ride log access code and the hash the server checks.

  python scripts/hash_code.py              make a new random code and print its hash
  python scripts/hash_code.py MY-CODE      print the hash of a code you chose

Put ONLY the hash into Vercel: Project -> Settings -> Environment Variables -> RIDE_LOG_CODE_SHA256.
Share the code with friends inside the link: https://live-nammametro-simulation.vercel.app/ride-log/#code=<code>
Never commit the code or the hash to the repo. To change the code later, set a new hash and share a new link
(phones with the old code keep their taps and upload once they open the new link).
"""
import hashlib, secrets, sys

ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'   # no look-alike characters
code = sys.argv[1].strip() if len(sys.argv) > 1 else '-'.join(''.join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3))
print('access code          :', code)
print('RIDE_LOG_CODE_SHA256 :', hashlib.sha256(('namma-ride-log:' + code).encode()).hexdigest())
print('link for friends     : https://live-nammametro-simulation.vercel.app/ride-log/#code=' + code)
