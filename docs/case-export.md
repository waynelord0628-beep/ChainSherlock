# Case Export and Import

Supported package modes:

- `full`: safe case metadata, policy-allowed evidence, registered artifacts, reports
  and audit records.
- `report_only`: reports and the minimum safe case summary.
- `deidentified`: redacted structured results and reports without original evidence.

Every `.chainsherlock-case.zip` contains a manifest with relative paths, sizes and
SHA-256 hashes. Secrets, environment files, caches, temporary files and unregistered
workspace content are excluded.

Import rejects absolute paths, traversal, backslashes, symlinks, duplicate entries,
oversized files, excessive total size, suspicious compression ratios and hash
mismatches. Validation completes in a temporary directory before a new case ID is
committed. The imported case records source-case provenance and never overwrites an
existing workspace.
