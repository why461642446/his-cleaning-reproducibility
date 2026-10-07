# K1 independent OOD lexical transformation: `OOD_LEX_MULTI_01`

## Purpose and preregistered boundary

This condition is an isolated, post-HELDOUT diagnostic experiment. It does not
alter, replace, or pool with the frozen 25-condition internal HELDOUT results.
It tests a transformation operator not used in the retained six-mechanism
HELDOUT mixture: one adjacent alphabetic-character transposition plus one
distinct alphabetic-character deletion in a diagnosis name.

The diagnosis code is deliberately retained. Thus the condition tests
code-supported recovery after a multi-character lexical deformation; it is not
evidence of dictionary-free name-only generalization.

## Frozen construction

- Source: canonical reference tables.
- Seed: `20260925`.
- Events: 1,900 diagnosis-name events.
- Operator: exactly one adjacent alphabetic-character transposition and one
  deletion at a distinct alphabetic position.
- Required response: `CORRECT` to the source canonical diagnosis name.
- Cleaner: unmodified `FULL_FRAMEWORK_V3`.
- Evaluation: isolated ground truth and the retained 100,000 negative-state
  sample; no original HELDOUT condition was reopened or overwritten.

The condition protocol is recorded in
`work/ood_experiment/OOD_LEX_MULTI_01/protocol.json`.

## Result

| Quantity | Result |
|---|---:|
| Injected events | 1,900 |
| Successful event recoveries (TP) | 1,900 |
| Missed injected events (FN) | 0 |
| Event recall | 1.000000 |
| Correct edits | 1,900 |
| Incorrect edits | 1 |
| Edit precision | 0.999474 |
| Recovery accuracy | 1.000000 |
| Newly invalid sampled negative states | 0 / 100,000 |

The 1,900 recoveries were made through the frozen lexical and semantic stages:
1,233 `M1` lexical-fuzzy corrections and 667 `M2` code-to-canonical-name
standardizations. This composition confirms that the test is code-supported.

## Important metric qualification

The universal evaluator also counted 8,582 unrelated actions already triggered
by the uncorrupted full tables (principally numeric `FLAG` actions). It therefore
reported a global action Precision of 0.181263 for this isolated condition. That
quantity is not a precision estimate for the 1,900 lexical injections and must
not be compared with the original HELDOUT mixture precision. The event-level
result for this condition is 1,900/1,900 recovery.

## Interpretation

The result expands the tested lexical transformation family beyond the original
single-character HELDOUT typo operator. It weakens, but does not eliminate, the
generator-family limitation: both transformations remain synthetic and retain
the diagnosis code. The separately completed alias experiment remains the
relevant evidence for dictionary-external terminology, and its code-masked arm
showed no name-only recovery. These experiments should be reported as
mechanism-specific diagnostic evidence, not as a population prevalence estimate
or proof of broad real-world lexical generalization.
