# Release notes — v1.0.2

This corrective release does not change the frozen FULL_FRAMEWORK_V3 cleaner,
its rules, or its thresholds.

Changes relative to v1.0.1:

- adds the serial-action-attribution evaluator used by the current manuscript;
- preserves the historical cleaner as a byte-exact Git artifact so checkout
  line-ending conversion cannot invalidate the wrapper SHA-256 check;
- records the evaluator SHA-256 and the expected seed-42/5% manuscript metrics;
- clarifies that the earlier evaluator is retained only for legacy-result
  provenance.

The serial-attribution evaluator SHA-256 is
`58bedfc98ca9b7a375a558d0423bd682432b165ba4907d056fac128c7a55f918`.
