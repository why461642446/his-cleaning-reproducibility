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

## Required before publication

- [x] Apply MIT to the public code and CC BY 4.0 to the separately archived
      synthetic benchmark.
- [ ] Run the documented smoke test in a fresh environment.
- [x] Create a public GitHub repository and replace the repository placeholder
      in `CITATION.cff`.
- [x] Publish the separate Zenodo dataset as version 1.0.0 under DOI
      `10.5281/zenodo.23209036` and add it to `README.md`.
- [ ] Create GitHub tag `v1.0.1` and archive that software release in Zenodo.
- [x] Add the public repository and dataset DOI to manuscript version 26.

## Never publish

- MIMIC-IV source files or extracts.
- Patient-level MIMIC-derived tables, samples, action logs, or review sheets.
- PhysioNet credentials, certificates, DUA documents, or account screenshots.
- Local configuration files containing private filesystem paths.
