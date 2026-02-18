# Homebrew Packaging

## Install

```bash
brew tap provara-protocol/provara
brew install provara
```

## Local Formula Test

```bash
brew install --build-from-source tools/packaging/homebrew/provara.rb
provara --help
```

## Update Process

1. Upload new release to PyPI.
2. Fetch sdist URL + SHA256:
   ```bash
   python -c "import json,urllib.request;d=json.load(urllib.request.urlopen('https://pypi.org/pypi/provara-protocol/<VERSION>/json'));f=[x for x in d['urls'] if x['packagetype']=='sdist'][0];print(f['url']);print(f['digests']['sha256'])"
   ```
3. Update `url` and `sha256` in `provara.rb`.
4. Commit and tag.
