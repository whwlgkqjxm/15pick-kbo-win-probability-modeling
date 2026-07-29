# Data release policy

This repository was assembled from a private research archive. It distinguishes the current
**private review build** from either a **data-minimized public build** or an unrestricted public
release that retains the derived KBO data.

This document is an operational release-control policy. It is not legal advice and does not decide
ownership, copyright, database, contract, privacy, or other rights. Public accessibility of a source
page does not by itself establish permission to redistribute data derived from that source.

## Current release decision

- **Current build:** private review build.
- **Unrestricted public release of the restricted artifacts below:** no redistribution basis or approval record is included in this repository.
- **Exact 1,824-game reproduction from included data:** available only in the private review build.
- **Default action:** keep this build private until Path A or Path B is completed and recorded.

Project-authored code, documentation, schemas, aggregate summaries, integrity records, tests, and
synthetic examples are suitable for controlled portfolio review and are candidates for a
data-minimized public build after a final release scan. That statement does not clear the
restricted artifacts below for unrestricted redistribution.

## Restricted review-artifact inventory

Until a documented public-release decision is completed, treat the following files as private
review artifacts:

| File | Row-level contents |
|---|---|
| [`data/derived/V12_MODELING_DATASET.csv`](../data/derived/V12_MODELING_DATASET.csv) | 1,824 game rows and 71 columns, including official-derived game identifiers, outcomes, starter names and IDs, pregame features, and role-index inputs |
| [`reports/frozen/V12_2026_ALL_PREDICTIONS.csv`](../reports/frozen/V12_2026_ALL_PREDICTIONS.csv) | 416 games with outcomes and 130 candidate probability columns |
| [`reports/frozen/V12_2026_BATTER_ABLATION_PREDICTIONS.csv`](../reports/frozen/V12_2026_BATTER_ABLATION_PREDICTIONS.csv) | 416 games with outcomes and batter-ablation probabilities |
| [`reports/reproduced/player_index_ablation_predictions.csv`](../reports/reproduced/player_index_ablation_predictions.csv) | 832 protocol-game rows with identifiers, outcomes, and reproduced probabilities |
| [`research_records/key_results/V10_PREDICTIONS.csv`](../research_records/key_results/V10_PREDICTIONS.csv) | 6,684 historical model-game rows with identifiers, outcomes, and probabilities |

Any future artifact containing row-level official game or player identifiers, outcomes, source-derived
features, or game-level predictions inherits the same restricted status until it is reviewed and
recorded here.

## Materials allowed in the private review build

- maintained research code and tests;
- documentation, schemas, synthetic examples, and aggregate result summaries;
- the restricted derived table and row-level prediction artifacts listed above;
- fitted model binaries and model schemas;
- audit reports, research decisions, environment records, and SHA256 integrity records.

## Materials never included

- complete raw KBO HTTP responses or the BoxScore cache;
- operational website databases, betting records, user assets, pricing, or settlement data;
- credentials, private keys, access tokens, private user or account records, contact information,
  or other non-public personal data;
- any artifact whose redistribution is known to be prohibited or for which required permission has
  been denied.

## License boundary

The MIT license in [`LICENSE`](../LICENSE) applies to the project-authored software and associated
project documentation within its stated scope. It does not by itself grant rights to KBO-origin
records, official identifiers, third-party material, or the restricted derived and row-level output
files listed above. No public data license is granted for those files unless Path A is completed and
the resulting decision is recorded explicitly.

## Public-data release gate

Before making restricted artifacts reachable through an unrestricted public repository, release,
mirror, or downloadable archive, complete one of the following paths.

### Path A — retain the included derived table and row-level outputs

1. Review the source terms, licenses, and any written permission applicable at the intended release
   date. Do not infer redistribution permission merely because the source records are publicly
   viewable.
2. Record the source owner or controller, the applicable terms or permission, the reviewed version
   or URL and date, the allowed redistribution and modification scope, commercial or non-commercial
   limits, and required attribution.
3. Record the reviewer or approver, the decision date, and the exact covered file paths and SHA256
   values. A general approval statement is not enough.
4. Keep raw official responses, source caches, and all operational 15Pick data excluded.
5. Update the repository documentation, manifest, and release notes so the granted scope and any
   continuing restrictions are visible to downstream users.

### Path B — publish a data-minimized repository

1. Remove the restricted inventory above and any equivalent future row-level artifacts from the
   public tree.
2. Review fitted model binaries separately. Do not assume that removing row-level CSV files alone
   determines whether binaries trained from those data are suitable for public redistribution; if
   no documented basis is available, omit the binaries and retain schemas and aggregate summaries.
3. If restricted artifacts were ever reachable on a public remote, remove them from all public
   branches, tags, releases, Git LFS objects, downloadable archives, and other reachable Git
   references. Review known forks and pull-request references. Deleting files only in the latest
   commit, or later changing repository visibility, is not a complete history-removal procedure.
4. Update the reproduction scripts, Makefile targets, tests, and CI so the public build does not
   require removed data. Use synthetic fixtures and aggregate verification where appropriate.
5. Update the README and reproducibility documentation so they no longer claim that public users can
   rerun the 1,824-game analysis from included data.
6. Rebuild the SHA256 manifest, create release archives only from the sanitized tree, and run a final
   scan for restricted files, secrets, private paths, and unexpected third-party assets.

## Maintenance rule

Any change to the release decision must be reflected in this file, `README.md`, `README.ko.md`,
`data/derived/README.md`, `reports/README.md`, `research_records/README.md`, `docs/data_card.md`,
`docs/limitations.md`, and `docs/reproducibility.md`. If the included artifact set changes, rebuild
the SHA256 research manifest and every downloadable release archive before publication.
