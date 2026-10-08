# Public release checklist

## Completed locally

- [x] Created an isolated public-code staging directory.
- [x] Confirmed that no MIMIC-IV data or patient-level derivatives are present.
- [x] Removed local user paths from the retained MIMIC acceptance report.
- [x] Made baseline, OOD, and scalability helper scripts path-configurable.
- [x] Preserved the byte-identical frozen V3 source; its historical path is
      replaced only in a temporary execution copy by the public wrapper.
- [x] Compiled every Python file successfully.
- [x] Generated a public-code SHA-256 manifest.
- [x] Generated a 128-file SHA-256 inventory for the synthetic-data deposit.
- [x] Completed the independent seed-42/rate-05 clean-machine reproduction.
- [x] Reproduced corrected serial-attribution metrics from both action logs.
- [x] Verified byte preservation of the frozen cleaner, corrected evaluator,
      and audit PDF through a fresh Git index export.

## Required before publication

- [x] Apply MIT to the public code and CC BY 4.0 to the separately archived
      synthetic benchmark.
- [x] Run the documented smoke test in a fresh environment.
- [x] Create a public GitHub repository and replace the repository placeholder
      in `CITATION.cff`.
- [x] Publish the separate Zenodo dataset as version 1.0.1 under DOI
      `10.5281/zenodo.23214371` and add it to `README.md`.
- [x] Retain the historical GitHub tag and release `v1.0.1`.
- [ ] Create and publish the corrective GitHub tag and release `v1.0.2`.
- [ ] Archive the software release in Zenodo and add its software DOI after
      verifying the GitHub–Zenodo import.
- [x] Publish the Zenodo dataset maintenance version `1.0.1` with unchanged
      data archives and updated license and metadata documentation.
- [x] Add the public repository and dataset DOI to manuscript version 26.

## Never publish

- MIMIC-IV source files or extracts.
- Patient-level MIMIC-derived tables, samples, action logs, or review sheets.
- PhysioNet credentials, certificates, DUA documents, or account screenshots.
- Local configuration files containing private filesystem paths.
