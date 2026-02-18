# IETF Internet-Draft Build Tools

This directory contains tools for building and submitting the Provara IETF Internet-Draft.

## Quick Start

```bash
# Install xml2rfc
pip install xml2rfc

# Build all formats
./tools/ietf/build.sh
```

## Output Files

The build script produces:

| File | Purpose |
|------|---------|
| `draft-hunt-provara-protocol-00.txt` | Plain text for submission |
| `draft-hunt-provara-protocol-00.html` | HTML for easy reading |
| `draft-hunt-provara-protocol-00.prepped.xml` | Expanded XML for review |

## Submission Process

### 1. Review

Before submission, review the generated text file:

```bash
cat tools/ietf/output/draft-hunt-provara-protocol-00.txt
```

Check for:
- Formatting issues
- Broken references
- ASCII art rendering
- Section numbering

### 2. Submit to IETF

1. Go to [IETF Submission Tool](https://datatracker.ietf.org/submit/)
2. Log in with your IETF account (create one if needed)
3. Select "Submit an Internet-Draft"
4. Upload `tools/ietf/output/draft-hunt-provara-protocol-00.txt`
5. Fill in metadata:
   - **Document name:** draft-hunt-provara-protocol-00
   - **Category:** Informational
   - **Stream:** Independent Submission
6. Review and submit

### 3. Post-Submission

After submission:
- You will receive a confirmation email
- The draft will appear at https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/
- Wait for automatic validation (usually < 24 hours)
- Address any issues flagged by the automated checker

## Versioning

Internet-Drafts use sequential versioning:

- `draft-hunt-provara-protocol-00.xml` — Initial submission
- `draft-hunt-provara-protocol-01.xml` — First revision
- `draft-hunt-provara-protocol-02.xml` — Second revision

Each revision increments the version number. IETF keeps all versions available.

## Draft Lifecycle

```
Submission → Validation → Publication → Expiration (6 months)
                ↓
        Community Review
                ↓
           Revision (-01, -02, ...)
                ↓
        WG Adoption (optional)
                ↓
        Standards Track (optional)
```

**Note:** This draft is submitted as Informational, not Standards Track. It documents the Provara protocol for interoperability and reference.

## XML Structure

The draft uses xml2rfc v3 format (RFC 7991):

```xml
<rfc version="3" category="info" docName="draft-hunt-provara-protocol-00">
  <front>
    <title>Provara: A Self-Sovereign Cryptographic Event Log Protocol</title>
    <author initials="H." surname="Hunt">
      <organization>Hunt Information Systems LLC</organization>
    </author>
    <date year="2026"/>
    <abstract>...</abstract>
  </front>
  <middle>
    <!-- Content sections -->
  </middle>
  <back>
    <!-- References and appendices -->
  </back>
</rfc>
```

## References

References are split into normative and informative:

**Normative:**
- RFC 2119 (Key words)
- RFC 8032 (Ed25519)
- RFC 8785 (Canonical JSON)
- FIPS 180-4 (SHA-256)
- FIPS 186-5 (Digital signatures)

**Informative:**
- RFC 6962 (Certificate Transparency)
- RFC 3161 (Timestamp Protocol)
- IETF SCITT Working Group documents
- Academic papers on quantum computing, threat modeling

## Common Issues

### xml2rfc not found

```bash
pip install xml2rfc
```

### Reference resolution fails

Ensure all referenced RFCs are available. xml2rfc fetches them automatically from the IETF repository.

### ASCII art formatting

Check ASCII art in the text output. Adjust spacing in the XML if lines wrap incorrectly.

### ID nits

After submission, the IETF ID Nits tool will check for issues:

```bash
# Run locally (optional)
idnits tools/ietf/output/draft-hunt-provara-protocol-00.txt
```

Common nits:
- Obsolete references
- Missing boilerplate
- Line length > 72 characters

## Resources

- [xml2rfc Documentation](https://xml2rfc.tools.ietf.org/xml2rfc-doc.html)
- [IETF Submission Tool](https://datatracker.ietf.org/submit/)
- [ID Nits Tool](https://tools.ietf.org/tools/idnits/)
- [RFC 7991 (xml2rfc v3 Format)](https://www.rfc-editor.org/rfc/rfc7991)
- [RFC 7322 (I-D Style Guide)](https://www.rfc-editor.org/rfc/rfc7322)

## Contact

For questions about the Provara I-D:
- Email: contact@provara.dev
- GitHub: https://github.com/provara-protocol/provara/issues
