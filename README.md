# hadoop-practice

Practicing Big Data with Hadoop.

---

## Unduplicated Client & Family-Level Program Reach Analyzer

`client_enrollment_dedup.py` is a Google Colab-ready Python/pandas tool that
turns a program-enrollment export into accurate, **unduplicated** counts of
clients and families served — and separately reports **adjusted family reach**
for programs that cover the whole household even when only some members were
formally enrolled.

### Quick start (Google Colab)

1. Upload `client_enrollment_dedup.py` to your Colab session (or paste it into a
   cell).
2. Run it. It first builds a synthetic dataset and prints the verification
   tests, then prompts you to upload your real file:

   ```python
   !pip -q install pandas openpyxl
   %run client_enrollment_dedup.py
   ```

3. When prompted, upload your CSV/Excel enrollment file (and, optionally, a
   separate client-roster file). A formatted workbook
   `unduplicated_client_analysis.xlsx` is produced. The original upload is never
   modified.

You can also run it locally:

```bash
pip install pandas openpyxl
python client_enrollment_dedup.py        # runs the verification tests
```

To analyze a file non-interactively, set `ENROLLMENT_FILE` (and optionally
`ROSTER_FILE`) in the **Configuration** section near the top of the script.

### Mapping your columns

Edit `COLUMN_MAP` in the configuration section. The **left** keys are fixed;
change the **right** values to your actual headers. Matching is
whitespace/case-insensitive, so headers like `"Case Size "` (trailing space) are
handled automatically. Set any optional field to `None` if it does not exist —
the script reports which calculations it can and cannot complete.

### Declaring family-level programs

List the programs that serve the whole family in `FAMILY_LEVEL_PROGRAMS`.
Matching is case-insensitive and space-tolerant. Use `FAMILY_PROGRAM_MATCH =
"exact"` (normalized exact match) or `"contains"` (substring match).

### Reporting period

Set `REPORT_START_DATE`, `REPORT_END_DATE` (served during a period) and
`AS_OF_DATE` (currently active). Leave the period `None` for all-time served;
leave `AS_OF_DATE` `None` to use today (printed for transparency).

### Output workbook

| Worksheet | Contents |
|-----------|----------|
| Organization Summary | Org-wide unduplicated totals + data-quality counts |
| Program Summary | Per-program documented counts vs. adjusted family reach |
| Family Program Detail | Per-case documented vs. adjusted reach + method + flags |
| Unique Client Detail | One deduplicated row per Alien Number |
| Data Quality | Every flagged issue, isolated by type |
| Reconciliation | Auditable chain raw → valid → unique → adjusted |
| Cleaned Enrollment Data | Cleaned rows with audit + flag columns |
| Cleaned Client Roster | Present only when a separate roster is supplied |

### Key rule

The individual (Alien Number), not the enrollment row, is the unit of the
organization-wide count. **The sum of per-program client counts is never the
organization-wide unduplicated total.** Documented enrollment and adjusted
family reach are always reported as two separate, clearly-labeled numbers, and
adjusted reach is never lower than documented enrollment.
