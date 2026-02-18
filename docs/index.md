# Provara Protocol Documentation

Provara is a self-sovereign cryptographic event log protocol for tamper-evident memory. Every event is signed, content-addressed, and chained so state can be replayed and verified independently on any compliant implementation.

The protocol is designed for long-horizon auditability and cross-implementation portability. The Python package is the reference implementation, with Rust and TypeScript implementations evolving toward shared conformance test vectors and interoperable vault verification.

## Quick install

```bash
pip install provara
```

## 30-second example

```bash
provara init My_Backpack
provara append My_Backpack --type OBSERVATION --data '{"subject":"system","predicate":"status","value":"ok"}' --keyfile My_Backpack/identity/private_keys.json
provara verify My_Backpack
```

## Continue reading

- [Getting Started](getting-started.md)
- [Tutorials](tutorials/README.md)
- [Cookbook](cookbook/README.md)
- [API Reference](api-reference/index.md)
- [Protocol Spec](protocol-spec.md)
