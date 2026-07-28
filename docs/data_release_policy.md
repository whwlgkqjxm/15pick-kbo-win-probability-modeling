# Data release policy

This repository was assembled from a private research archive. It separates materials by
redistribution risk and distinguishes a private review build from an unrestricted public release.

## Current release status

The code, documentation, schemas, aggregate results, integrity records, and synthetic examples are
suitable for portfolio review. The repository should remain private, or the files listed under the
public-data release gate below should be removed, until the redistribution basis for the derived KBO
table and game-level outputs has been reviewed and recorded.

This is a release-control statement, not a claim that the included derived data have already been
cleared for unrestricted redistribution.

## Included in the private review build

- maintained research code;
- the derived game-level feature table used for core reproduction;
- frozen aggregate results and game-level model probabilities;
- model binaries and schemas;
- audit reports, research decisions, and SHA256 records.

## Never included

- complete raw KBO HTTP responses or the BoxScore cache;
- operational website databases, betting records, user assets, pricing, or settlement data;
- credentials, private keys, access tokens, or personal data;
- any artifact known to contain third-party material that cannot be redistributed.

## Public-data release gate

Before making the repository unrestricted and public, complete one of the following paths.

### Path A — retain the released derived table

1. Record the basis for redistributing the derived game-level table, game identifiers, and
   game-level prediction outputs.
2. Record the review date and the exact files covered by that decision.
3. Keep the raw official responses and operational 15Pick data excluded.

### Path B — publish a data-minimized repository

1. Remove `data/derived/` and any row-level outputs that depend on the restricted table.
2. Retain code, schemas, aggregate result summaries, tests that use synthetic fixtures, and the
   historical research narrative.
3. Update the README and reproducibility page so they no longer claim that public users can rerun
   the 1,824-game analysis from included data.

## Maintenance rule

Any change to the public-data decision must be reflected in this file, the README,
[`docs/reproducibility.md`](reproducibility.md), and the SHA256 research manifest before release.
