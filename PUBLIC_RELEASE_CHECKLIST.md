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

- [ ] Confirm MIT for code and CC BY 4.0 for the synthetic data with both
      authors and verify that no upstream component conflicts with CC BY 4.0.
- [ ] Run the documented smoke test in a fresh environment.
- [x] Create a public GitHub repository and replace the repository placeholder
      in `CITATION.cff`.
- [ ] Create a separate Zenodo dataset draft, upload the synthetic archive,
      reserve a DOI, and replace the dataset DOI placeholder in `README.md`.
- [ ] Create GitHub tag `v1.0.0` and archive that software release in Zenodo.
- [ ] Add the final software and dataset citations to the manuscript.

## Never publish

- MIMIC-IV source files or extracts.
- Patient-level MIMIC-derived tables, samples, action logs, or review sheets.
- PhysioNet credentials, certificates, DUA documents, or account screenshots.
- Local configuration files containing private filesystem paths.
