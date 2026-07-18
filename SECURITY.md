Security steps for handling leaked credentials

1) Remove secrets from repository files (done):
   - `config.py` no longer contains hardcoded credentials.

2) Add `.env` to `.gitignore` (already present) and use `.env.example` as template.

3) Purge secrets from git history (example commands):

# Using git filter-repo (recommended):
# Install: pip install git-filter-repo

git clone --mirror <repo-url> repo.git
cd repo.git
git filter-repo --invert-paths --path config.py  # or use --replace-text to scrub specific values
# push back
git push --force --all
git push --force --tags

# Using BFG (alternative):
# bfg --delete-files config.py repo.git
# or to replace secrets in all files:
# bfg --replace-text replacements.txt repo.git

4) Rotate compromised keys immediately:
   - In Tuya IoT Cloud delete or regenerate the AccessID/Secret and device keys.
   - Invalidate any local keys and re-pair devices if necessary.

5) After rotation, update your `.env` with new values and do NOT commit it.

6) Notify collaborators and downstream consumers if secrets were exposed publicly.

If you want, I can:
- Generate the exact `git filter-repo` or `bfg` commands tailored to your repo and run them (requires confirmation), or
- Provide a step-by-step interactive guide to rotate Tuya keys in the Tuya IoT console.
