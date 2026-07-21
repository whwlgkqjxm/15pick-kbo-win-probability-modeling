# Data release policy

This repository was assembled from a private research archive. It separates materials by redistribution risk.

## Included

- maintained research code;
- derived game-level feature table used for core reproduction;
- frozen aggregate results and game-level model probabilities;
- model binaries and schemas;
- audit reports, decisions, and hashes.

## Not included

- complete raw KBO HTTP responses and BoxScore cache;
- operational website databases, betting, user assets, or pricing records;
- credentials, private keys, tokens, or personal data;
- artifacts whose redistribution rights are unclear.

## Before public release

1. Confirm the intended use of derived KBO tables and game identifiers.
2. Remove `data/derived` or provide a public-release-safe transformation if necessary.
3. Keep code, schemas, aggregate results, and synthetic examples even when full derived data is removed.
4. Never commit raw official responses without reviewing applicable terms.
