# K6 HoloClean Knowledge-Parity DEV Feasibility v1

## Question

Can the retained HoloClean implementation consume the same canonical diagnosis code--name reference relation available to frozen V3, without receiving any clean HELDOUT row-level values or event-level ground truth?

## Fixed DEV-only setup

- Input: deterministic 10,000-row diagnosis sample from `phase3_development/seed_20260922/corruption_05`.
- Reference: the canonical diagnosis code--name relation used by V3 to build its internal diagnosis dictionary (100 distinct code/title pairs).
- Excluded: event truth, V3 output, all HELDOUT directories, and any final-test result.
- HoloClean settings: same retained feasibility settings as the sealed common-scope run: 10 epochs, one thread, weak-label threshold 0.99, and both domain thresholds equal to zero.
- Attempted knowledge-equivalent constraint: code equality between dirty diagnosis row and canonical dictionary row, with inequality between their diagnosis-name values.
- Environment: retained local HoloClean installation and an isolated local PostgreSQL database created solely for this DEV feasibility test.

## Result

HoloClean loaded the 10,000 dirty rows and the 100-row canonical dictionary and parsed the cross-table denial constraint. Its built-in `ViolationDetector` then terminated before repair with:

`ERROR in violation detector. Cannot ground mult-tuple template.`

No HoloClean repair output, score, or HELDOUT result was produced. The failure occurred before ground truth could be accessed, and the pilot script does not contain any ground-truth or V3-output path.

## Interpretation

The retained HoloClean path can run the earlier same-table, code/name consistency baseline, but it cannot directly execute the attempted cross-table canonical-dictionary configuration through its standard violation detector. Therefore the previous HoloClean results remain a **restricted common-scope baseline**, not a knowledge-equivalent full comparison.

This is an implementation/interface limitation, not evidence that HoloClean is ineffective. It would be invalid to report a zero repair score for this attempted configuration because no repair phase was reached.

## Consequence for the manuscript

Retain the existing restricted HoloClean table only with its scope warning. Add a short feasibility statement:

> A DEV-only knowledge-parity feasibility test supplied HoloClean with the same canonical diagnosis code--name relation available to the proposed framework, without event truth or HELDOUT values. The retained implementation parsed but could not ground the required cross-table dictionary constraint in its standard violation detector; therefore no knowledge-equivalent HoloClean repair result is claimed.

Do not claim a complete HoloClean head-to-head benchmark. A future fair comparison would require a HoloClean-compatible immutable-reference adapter, a different external baseline that natively accepts master-data joins, or a documented custom extension; each would be a new baseline implementation rather than an unchanged off-the-shelf run.
