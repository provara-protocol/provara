# winget Manifest Notes

This folder contains a draft winget manifest for `provara-protocol` version `1.0.0`.

Current distribution is via PyPI (`pip install provara-protocol`). The manifest tracks
that release artifact and metadata so the winget package can be prepared.

## Submission Process (winget-pkgs)

1. Fork `https://github.com/microsoft/winget-pkgs`.
2. Create the standard path:
   `manifests/p/provara-protocol/Provara/1.0.0/`
3. Add/update manifest files (singleton or split schema per repo guidelines).
4. Run validation:
   ```powershell
   winget validate <manifest path>
   ```
5. Open PR to `microsoft/winget-pkgs` with release notes and installer hashes.
6. Address automated and maintainer review feedback until merged.

## Practical Install Today

```powershell
python -m pip install provara-protocol
provara --help
```
