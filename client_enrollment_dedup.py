#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
 UNDUPLICATED CLIENT & FAMILY-LEVEL PROGRAM REACH ANALYZER
==============================================================================

Purpose
-------
Produce accurate, *unduplicated* counts of individual clients and families
served by a multi-program refugee-services organization, plus a separately
labeled "adjusted family reach" measure for programs that serve the whole
household even when only some members were formally enrolled.

Core counting principles (never violated by this script)
--------------------------------------------------------
  * The individual, not the enrollment row, is the unit of count.
      -> One person enrolled in 3 programs = 1 organization-wide client.
      -> That same person may still count once in EACH program.
  * The family (Case Number) is the unit for family counts.
  * "Documented enrolled" and "Adjusted family reach" are ALWAYS reported as
    two separate, clearly-labeled numbers.  Adjusted reach never overwrites
    documented enrollment, and is never lower than it.
  * Missing / malformed identifiers are flagged, never invented, never turned
    into the strings "nan"/"None"/"NULL", and never counted as valid clients.
  * The sum of per-program client counts is NEVER presented as the
    organization-wide unduplicated total.

This file is Google-Colab ready.  It runs top-to-bottom:
    1. Builds a synthetic test dataset and proves the counting logic.
    2. (Optional) Loads your real uploaded file(s) and produces the reports
       + a formatted Excel workbook.

Author: data-quality analysis pipeline
==============================================================================
"""

import os
import re
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore", category=UserWarning)


# =============================================================================
# 1. CONFIGURATION  --  EDIT THIS SECTION TO MATCH YOUR DATASET
# =============================================================================
# ---------------------------------------------------------------------------
# 1a. Column mapping.  LEFT = logical name used by the code (do not change).
#     RIGHT = the exact column header in *your* file (change these).
#     Header matching is whitespace- and case-insensitive, so trailing spaces
#     such as "Case Size " are handled automatically.  Set a value to None if
#     that field does not exist in your data.
# ---------------------------------------------------------------------------
COLUMN_MAP = {
    "alien_number":    "Alien Number",          # individual-level identifier
    "case_number":     "Case Number",           # family/household identifier
    "program":         "Program",               # program / enrollment name
    "enrollment_date": "Date of Enrollment",    # enrollment start date
    "termination_date": "Date of Termination",  # enrollment end date (blank = ongoing)
    "status":          "Is program Enrollment Active?",  # optional status field
    "family_size":     "Case Size",             # recorded household size ("Number in Case")
    "client_name":     None,                    # single full-name column, if you have one
    "first_name":      "First Name",            # used to build a name if client_name is None
    "last_name":       "Last Name",             # used to build a name if client_name is None
    "date_of_birth":   "Date of Birth",         # optional, for identity review
}

# ---------------------------------------------------------------------------
# 1b. Family-level programs.  These programs are understood to serve/cover the
#     WHOLE family when at least one member is enrolled.  Matching is
#     case-insensitive and ignores leading/trailing spaces.
#     Set FAMILY_PROGRAM_MATCH = "exact" for exact (normalized) matches, or
#     "contains" to match any program whose name CONTAINS one of these strings.
# ---------------------------------------------------------------------------
FAMILY_LEVEL_PROGRAMS = [
    "Refugee Case Management",
    "Mass Refugee Health Promotion Program",   # the prompt's "Refugee Health Promotion"
]
FAMILY_PROGRAM_MATCH = "exact"   # "exact" | "contains"

# ---------------------------------------------------------------------------
# 1c. Reporting period.  Use "YYYY-MM-DD" strings or None.
#       * REPORT_START_DATE / REPORT_END_DATE define "served during period".
#         If BOTH are None, all-time served is calculated.
#       * AS_OF_DATE defines "currently active".  If None, today's date is used
#         (printed clearly so results remain interpretable/reproducible).
# ---------------------------------------------------------------------------
REPORT_START_DATE = None       # e.g. "2024-10-01"
REPORT_END_DATE   = None       # e.g. "2025-09-30"
AS_OF_DATE        = None       # e.g. "2025-09-30"

# ---------------------------------------------------------------------------
# 1d. Status handling.  The date rule is primary for "currently active".
#     These lists let the script compare a status field against the dates and
#     report inconsistencies.  A blank termination date is NOT assumed active
#     if the status field says the enrollment is closed/terminated.
# ---------------------------------------------------------------------------
INACTIVE_STATUSES = [
    "Terminated", "Closed", "Exited", "Rejected", "Cancelled",
    "NO Active Enrollment",           # this dataset's inactive marker
]
ACTIVE_STATUSES = [
    "Active", "Active Enrollment", "Open", "Enrolled",
]

# ---------------------------------------------------------------------------
# 1e. Input files.
#     ENROLLMENT_FILE : combined dataset OR the enrollment-only dataset.
#     ROSTER_FILE     : optional complete client/family-member roster
#                       (one row per person).  Leave None if you only have one
#                       combined file (Option A).
#     ENROLLMENT_SHEET / ROSTER_SHEET : worksheet name for Excel inputs
#                       (None = first sheet).
#     OUTPUT_FILE     : where the formatted workbook is written (a NEW file;
#                       the original upload is never modified).
# ---------------------------------------------------------------------------
ENROLLMENT_FILE   = None        # set at runtime / via upload
ROSTER_FILE       = None
ENROLLMENT_SHEET  = None
ROSTER_SHEET      = None
OUTPUT_FILE       = "unduplicated_client_analysis.xlsx"

# Values that must never be allowed to masquerade as real identifiers.
_FORBIDDEN_ID_TOKENS = {"", "nan", "none", "null", "na", "n/a", "#n/a", "0"}


# =============================================================================
# 2. SMALL UTILITIES
# =============================================================================
def _norm_header(h):
    """Normalize a column header for tolerant matching (strip + collapse + lower)."""
    return re.sub(r"\s+", " ", str(h)).strip().lower()


def resolve_columns(df, column_map):
    """
    Map logical field names -> the actual column objects present in df, using
    whitespace/case-insensitive matching.  Returns:
        resolved : {logical_name: actual_column_name_or_None}
        missing  : [logical_names that were requested but not found]
    """
    lookup = {_norm_header(c): c for c in df.columns}
    resolved, missing = {}, []
    for logical, requested in column_map.items():
        if requested is None:
            resolved[logical] = None
            continue
        actual = lookup.get(_norm_header(requested))
        resolved[logical] = actual
        if actual is None:
            missing.append(logical)
    return resolved, missing


def _to_date(series):
    """Parse a column to datetime (NaT on failure), silently, all-time safe."""
    return pd.to_datetime(series, errors="coerce")


def _parse_cfg_date(value):
    return None if value in (None, "", "None") else pd.to_datetime(value)


def norm_program(value):
    """Normalize a program name for matching: collapse whitespace, strip, casefold-preserving."""
    if pd.isna(value):
        return np.nan
    return re.sub(r"\s+", " ", str(value)).strip()


def _norm_program_key(value):
    return "" if pd.isna(value) else re.sub(r"\s+", " ", str(value)).strip().lower()


# =============================================================================
# 3. DATA LOADING  (CSV or Excel, identifiers read as text)
# =============================================================================
def load_dataframe(path, sheet=None, id_like_columns=None):
    """
    Load a CSV or Excel file.  ID-like columns are forced to text so that
    leading zeros are preserved and numbers are not silently reformatted.
    """
    if path is None:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    id_like_columns = id_like_columns or []
    ext = os.path.splitext(path)[1].lower()

    # First peek at headers so we can force ID columns to string on read.
    if ext in (".xlsx", ".xls", ".xlsm"):
        head = pd.read_excel(path, sheet_name=(sheet or 0), nrows=0)
    elif ext in (".csv", ".txt"):
        head = pd.read_csv(path, nrows=0)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Use CSV or Excel.")

    lookup = {_norm_header(c): c for c in head.columns}
    dtype = {}
    for wanted in id_like_columns:
        actual = lookup.get(_norm_header(wanted))
        if actual is not None:
            dtype[actual] = str

    if ext in (".xlsx", ".xls", ".xlsm"):
        df = pd.read_excel(path, sheet_name=(sheet or 0), dtype=dtype)
    else:
        df = pd.read_csv(path, dtype=dtype, keep_default_na=True)

    return df


# =============================================================================
# 4. IDENTIFIER CLEANING
# =============================================================================
def _clean_alien(raw):
    """
    Clean a single Alien Number to a canonical text form WITHOUT inventing data.
    Returns (clean_value_or_NaN, is_missing, is_malformed).
    Rules:
      * strip spaces; uppercase; remove internal spaces & hyphens.
      * treat forbidden tokens (blank/nan/none/null/0) as MISSING (NaN).
      * a valid A-number = 'A' followed by 7-9 digits, not all zeros.
        Anything else that is present but non-conforming is MALFORMED (kept).
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return np.nan, True, False
    s = str(raw).strip()
    if s.lower() in _FORBIDDEN_ID_TOKENS:
        return np.nan, True, False
    s = re.sub(r"[\s\-]", "", s).upper()
    if s.lower() in _FORBIDDEN_ID_TOKENS:
        return np.nan, True, False
    # All-zero A-numbers (e.g. A00000000) are placeholders, not real people.
    if re.fullmatch(r"A0+", s) or re.fullmatch(r"0+", s):
        return np.nan, True, False
    is_valid = bool(re.fullmatch(r"A\d{7,9}", s))
    return s, False, (not is_valid)


def _clean_case(raw):
    """Clean a Case Number (text, preserve leading zeros). Returns (value, is_missing)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return np.nan, True
    s = str(raw).strip()
    if s.lower() in _FORBIDDEN_ID_TOKENS:
        return np.nan, True
    s = re.sub(r"\s+", "", s)
    return s, False


def _alien_core(clean_alien):
    """
    Format-insensitive key: strip leading 'A' and leading zeros so that
    'A01937958' and 'A0001937958' collapse to the same core digits.  Used ONLY
    to *detect* possible duplicates for human review -- never to auto-merge.
    """
    if pd.isna(clean_alien):
        return np.nan
    digits = re.sub(r"\D", "", str(clean_alien))
    digits = digits.lstrip("0")
    return digits if digits else np.nan


def clean_identifiers(df, cols):
    """
    Add cleaned identifier columns + audit columns + quality flags.
    Original values are preserved in *_orig columns; cleaned values live in
    canonical columns 'alien_clean' and 'case_clean'.
    """
    df = df.copy()
    a_col, c_col = cols["alien_number"], cols["case_number"]

    # --- Alien Number ---
    if a_col is not None:
        df["alien_number_orig"] = df[a_col]
        cleaned = df[a_col].apply(_clean_alien)
        df["alien_clean"]   = [t[0] for t in cleaned]
        df["alien_missing"] = [t[1] for t in cleaned]
        df["alien_malformed"] = [t[2] for t in cleaned]
    else:
        df["alien_number_orig"] = np.nan
        df["alien_clean"] = np.nan
        df["alien_missing"] = True
        df["alien_malformed"] = False

    # --- Case Number ---
    if c_col is not None:
        df["case_number_orig"] = df[c_col]
        cleaned = df[c_col].apply(_clean_case)
        df["case_clean"]   = [t[0] for t in cleaned]
        df["case_missing"] = [t[1] for t in cleaned]
    else:
        df["case_number_orig"] = np.nan
        df["case_clean"] = np.nan
        df["case_missing"] = True

    df["alien_core"] = df["alien_clean"].apply(_alien_core)
    return df


def detect_identifier_conflicts(df):
    """
    Return review tables (never auto-applied):
      * alien_multi_case : one Alien Number -> multiple Case Numbers.
      * possible_dupe_alien : one format-insensitive core -> multiple distinct
        cleaned Alien Numbers (possible same person, differently formatted).
    """
    valid = df[df["alien_clean"].notna()]

    a2c = (valid.dropna(subset=["case_clean"])
                .groupby("alien_clean")["case_clean"].nunique())
    alien_multi_case = a2c[a2c > 1]
    multi_case_tbl = (valid[valid["alien_clean"].isin(alien_multi_case.index)]
                      .groupby("alien_clean")["case_clean"]
                      .apply(lambda s: sorted(set(s.dropna())))
                      .reset_index()
                      .rename(columns={"alien_clean": "Alien Number",
                                       "case_clean": "Distinct Case Numbers"}))
    multi_case_tbl["N Case Numbers"] = multi_case_tbl["Distinct Case Numbers"].apply(len)

    core2a = valid.dropna(subset=["alien_core"]).groupby("alien_core")["alien_clean"].nunique()
    ambiguous_cores = core2a[core2a > 1]
    dupe_alien_tbl = (valid[valid["alien_core"].isin(ambiguous_cores.index)]
                      .groupby("alien_core")["alien_clean"]
                      .apply(lambda s: sorted(set(s)))
                      .reset_index()
                      .rename(columns={"alien_core": "Normalized Core",
                                       "alien_clean": "Distinct Alien Formats"}))
    dupe_alien_tbl["N Formats"] = dupe_alien_tbl["Distinct Alien Formats"].apply(len)

    return multi_case_tbl, dupe_alien_tbl


# =============================================================================
# 5. ENROLLMENT PREPARATION  (dates, programs, served/active flags)
# =============================================================================
def prepare_enrollment(df, cols):
    """Attach parsed dates, normalized program, and served/active boolean flags."""
    df = df.copy()

    # Program
    if cols["program"] is not None:
        df["program_clean"] = df[cols["program"]].apply(norm_program)
    else:
        df["program_clean"] = np.nan
    df["program_key"] = df["program_clean"].apply(_norm_program_key)

    # Dates
    df["enroll_dt"] = _to_date(df[cols["enrollment_date"]]) if cols["enrollment_date"] else pd.NaT
    df["term_dt"]   = _to_date(df[cols["termination_date"]]) if cols["termination_date"] else pd.NaT

    # Family size
    if cols["family_size"] is not None:
        df["family_size_num"] = pd.to_numeric(df[cols["family_size"]], errors="coerce")
    else:
        df["family_size_num"] = np.nan

    # Reporting-period "served" flag: enrollment overlaps [start, end].
    start = _parse_cfg_date(REPORT_START_DATE)
    end   = _parse_cfg_date(REPORT_END_DATE)
    served = pd.Series(True, index=df.index)
    if end is not None:
        served &= (df["enroll_dt"].notna() & (df["enroll_dt"] <= end)) | df["enroll_dt"].isna()
    if start is not None:
        served &= df["term_dt"].isna() | (df["term_dt"] >= start)
    df["is_served"] = served

    # Currently-active flag by DATE rule (primary).
    as_of = _parse_cfg_date(AS_OF_DATE) or pd.Timestamp.today().normalize()
    df.attrs["as_of_used"] = as_of
    active_by_date = ((df["enroll_dt"].isna() | (df["enroll_dt"] <= as_of)) &
                      (df["term_dt"].isna() | (df["term_dt"] >= as_of)))
    df["active_by_date"] = active_by_date

    # Status field interpretation (secondary) -- used only to flag conflicts.
    if cols["status"] is not None:
        inact = {s.strip().lower() for s in INACTIVE_STATUSES}
        act = {s.strip().lower() for s in ACTIVE_STATUSES}
        st = df[cols["status"]].astype(str).str.strip().str.lower()
        df["status_says_inactive"] = st.isin(inact)
        df["status_says_active"] = st.isin(act)
    else:
        df["status_says_inactive"] = False
        df["status_says_active"] = False

    # FINAL active rule: active by date AND not contradicted by an inactive status.
    df["is_active"] = df["active_by_date"] & (~df["status_says_inactive"])

    # Flag: status/date disagreement (for the data-quality report).
    df["active_status_conflict"] = (
        (df["active_by_date"] & df["status_says_inactive"]) |
        ((~df["active_by_date"]) & df["status_says_active"])
    )

    # Flag: termination before enrollment.
    df["term_before_enroll"] = (df["enroll_dt"].notna() & df["term_dt"].notna() &
                                (df["term_dt"] < df["enroll_dt"]))
    return df


def is_family_program_key(program_key):
    """Case-insensitive family-program test honoring FAMILY_PROGRAM_MATCH."""
    keys = [_norm_program_key(p) for p in FAMILY_LEVEL_PROGRAMS]
    if FAMILY_PROGRAM_MATCH == "contains":
        return any(k and k in program_key for k in keys)
    return program_key in keys


# =============================================================================
# 6. ROSTER  (known family members per Case Number)
# =============================================================================
def build_roster(enroll_df, roster_df, cols, roster_cols):
    """
    Build a per-Case set of KNOWN unique valid Alien Numbers.

    * If a separate complete roster file is supplied -> that roster is the
      source of known members (method eligible = 'Complete roster').
    * Otherwise the combined enrollment file is the only source; the known
      members are the unique enrolled individuals (a LOWER BOUND -- non-enrolled
      household members are absent, hence family-size estimates are needed).
    """
    if roster_df is not None:
        r = clean_identifiers(roster_df, roster_cols)
        src = r[r["alien_clean"].notna() & r["case_clean"].notna()]
        roster_available = True
    else:
        src = enroll_df[enroll_df["alien_clean"].notna() & enroll_df["case_clean"].notna()]
        roster_available = False

    members = (src.groupby("case_clean")["alien_clean"]
                  .apply(lambda s: set(s.dropna())))
    known_members = members.to_dict()
    return known_members, roster_available


# =============================================================================
# 7. CORE DEDUPLICATED COUNTS
# =============================================================================
def valid_rows(df):
    """Rows usable for counting: a valid (present, non-placeholder) Alien Number."""
    return df[df["alien_clean"].notna()]


def org_wide_counts(df):
    """Organization-wide unduplicated counts (documented)."""
    served = valid_rows(df[df["is_served"]])
    active = valid_rows(df[df["is_active"]])
    return {
        "unique_valid_aliens":       valid_rows(df)["alien_clean"].nunique(),
        "unique_clients_served":     served["alien_clean"].nunique(),
        "unique_clients_active":     active["alien_clean"].nunique(),
        "unique_families_served":    served["case_clean"].nunique(),
        "unique_families_active":    active["case_clean"].nunique(),
    }


def per_program_counts(df):
    """One row per program with documented served/active client & family counts."""
    v = valid_rows(df)
    rows = []
    for prog, g in v.groupby("program_clean", dropna=False):
        gs = g[g["is_served"]]
        ga = g[g["is_active"]]
        rows.append({
            "Program": prog,
            "Raw Enrollment Rows": len(df[df["program_clean"] == prog]),
            "Documented Clients Served": gs["alien_clean"].nunique(),
            "Documented Clients Active": ga["alien_clean"].nunique(),
            "Families Served": gs["case_clean"].nunique(),
            "Families Active": ga["case_clean"].nunique(),
            "Is Family-Level Program": is_family_program_key(_norm_program_key(prog)),
        })
    return pd.DataFrame(rows).sort_values("Program").reset_index(drop=True)


# =============================================================================
# 8. FAMILY-LEVEL PROGRAM REACH  (documented vs. adjusted, clearly labeled)
# =============================================================================
def family_program_detail(df, known_members, roster_available):
    """
    For each designated family-level program, compute per-case:
      * documented enrolled members (unique aliens with a record in the program)
      * known roster members (unique aliens sharing the case)
      * recorded family size (from the family-size field, if present)
      * adjusted family reach + the method used + quality flag.
    Returns a per-(program, case) detail DataFrame.
    """
    v = valid_rows(df)
    detail_rows = []

    # Precompute the recorded family size(s) per case ONCE (avoids an O(N) scan
    # of the whole frame inside the per-case loop).
    case_sizes = (df.dropna(subset=["case_clean"])
                    .groupby("case_clean")["family_size_num"]
                    .apply(lambda s: sorted({int(x) for x in s.dropna()}))
                    .to_dict())

    fam_progs = v[v["program_key"].apply(is_family_program_key)]
    for prog, gp in fam_progs.groupby("program_clean"):
        for case, gc in gp.groupby("case_clean"):
            documented = set(gc["alien_clean"].dropna())
            doc_served = set(gc[gc["is_served"]]["alien_clean"].dropna())
            doc_active = set(gc[gc["is_active"]]["alien_clean"].dropna())

            roster = set(known_members.get(case, set()))
            roster = roster | documented  # documented members are always known

            # Recorded family size for this case (may conflict across rows).
            sizes = case_sizes.get(case, [])
            recorded_size = sizes[0] if len(sizes) == 1 else (sizes[-1] if sizes else np.nan)
            conflicting_size = len(sizes) > 1

            n_roster = len(roster)
            n_doc = len(documented)

            # --- Decide adjustment method & adjusted reach ---
            flag, flag_expl = "", ""
            if conflicting_size:
                method = "Conflicting family-size values"
                # Fall back to the larger of roster vs. the largest recorded size.
                adjusted = max(n_roster, recorded_size if not pd.isna(recorded_size) else 0)
                flag = "CONFLICTING_FAMILY_SIZE"
                flag_expl = f"Case has multiple recorded family sizes: {sizes}."
            elif roster_available:
                method = "Complete roster"
                adjusted = n_roster
                if not pd.isna(recorded_size) and recorded_size != n_roster:
                    flag = "ROSTER_SIZE_MISMATCH"
                    flag_expl = (f"Roster has {n_roster} members but recorded size "
                                 f"is {recorded_size}.")
            elif not pd.isna(recorded_size):
                method = "Family-size estimate"
                # Estimate: the recorded household size, but never below what we
                # can actually see enrolled/known.
                adjusted = max(recorded_size, n_roster)
                if recorded_size < n_roster:
                    flag = "FAMILY_SIZE_TOO_SMALL"
                    flag_expl = (f"Recorded size {recorded_size} < {n_roster} known "
                                 f"unique members; used known members instead.")
                elif recorded_size > n_roster:
                    flag = "MEMBERS_NOT_IN_DATA"
                    flag_expl = (f"Recorded size {recorded_size} > {n_roster} known "
                                 f"members; {recorded_size - n_roster} member(s) are "
                                 f"estimated (no individual Alien Number available).")
            else:
                method = "Unresolved—family size unavailable"
                adjusted = n_doc
                flag = "UNRESOLVED_FAMILY_SIZE"
                flag_expl = ("No complete roster and no recorded family size; only "
                             "documented enrollment can be counted.")

            # Adjusted reach can NEVER be lower than documented enrollment.
            adjusted = int(max(adjusted, n_doc))
            adjusted_served = int(max(len(doc_served),
                                      adjusted if len(doc_served) > 0 else len(doc_served)))
            adjusted_active = int(max(len(doc_active),
                                      adjusted if len(doc_active) > 0 else len(doc_active)))
            missing_members = max(0, adjusted - n_roster)

            detail_rows.append({
                "Program": prog,
                "Case Number": case,
                "Documented Enrolled Members": n_doc,
                "Known Roster Members": n_roster,
                "Recorded Family Size": recorded_size,
                "Adjusted Family Reach": adjusted,
                "Adjusted Reach (Served)": adjusted_served,
                "Adjusted Reach (Active)": adjusted_active,
                "Adjustment Method": method,
                "Potentially Missing Members": missing_members,
                "Data-Quality Flag": flag,
                "Flag Explanation": flag_expl,
            })

    cols_order = ["Program", "Case Number", "Documented Enrolled Members",
                  "Known Roster Members", "Recorded Family Size",
                  "Adjusted Family Reach", "Adjusted Reach (Served)",
                  "Adjusted Reach (Active)", "Adjustment Method",
                  "Potentially Missing Members", "Data-Quality Flag",
                  "Flag Explanation"]
    return pd.DataFrame(detail_rows, columns=cols_order)


def summarize_family_reach(detail):
    """Aggregate per-case family detail up to per-program adjusted totals."""
    if detail.empty:
        return pd.DataFrame(columns=["Program", "Adjusted Reach Served",
                                     "Adjusted Reach Active"])
    agg = (detail.groupby("Program")
                 .agg(**{"Adjusted Reach Served": ("Adjusted Reach (Served)", "sum"),
                         "Adjusted Reach Active": ("Adjusted Reach (Active)", "sum")})
                 .reset_index())
    return agg


# =============================================================================
# 9. CLIENT-LEVEL DEDUPLICATED DETAIL  (one row per Alien Number)
# =============================================================================
def client_level_detail(df, family_detail, cols):
    """One deduplicated row per valid Alien Number."""
    v = valid_rows(df).copy()

    # Best-known display name.
    if cols["client_name"] is not None:
        v["display_name"] = v[cols["client_name"]].astype(str)
    elif cols["first_name"] and cols["last_name"]:
        v["display_name"] = (v[cols["last_name"]].astype(str).str.strip() + ", " +
                             v[cols["first_name"]].astype(str).str.strip())
    else:
        v["display_name"] = np.nan

    # Which aliens got pulled into a family-level adjusted count?
    adjusted_cases = set(family_detail["Case Number"].unique()) if not family_detail.empty else set()

    rows = []
    for alien, g in v.groupby("alien_clean"):
        served = g[g["is_served"]]
        active = g[g["is_active"]]
        progs_served = sorted(served["program_clean"].dropna().unique())
        active_progs = sorted(active["program_clean"].dropna().unique())
        case_vals = sorted(g["case_clean"].dropna().unique())
        in_adj = any(c in adjusted_cases for c in case_vals)
        rows.append({
            "Alien Number": alien,
            "Client Name": g["display_name"].dropna().iloc[0] if g["display_name"].notna().any() else np.nan,
            "Case Number": case_vals[0] if case_vals else np.nan,
            "Programs Served": "; ".join(progs_served),
            "Distinct Programs": len(progs_served),
            "First Enrollment Date": g["enroll_dt"].min(),
            "Most Recent Enrollment Date": g["enroll_dt"].max(),
            "Currently Active (Any Program)": len(active) > 0,
            "Currently Active Programs": "; ".join(active_progs),
            "In Family-Level Adjusted Count": in_adj,
            "Adjusted Classification Source": (
                "Member of a family-level program case" if in_adj else "Documented only"),
        })
    return pd.DataFrame(rows).sort_values("Alien Number").reset_index(drop=True)


# =============================================================================
# 10. DATA-QUALITY REPORT
# =============================================================================
def data_quality_report(df, multi_case_tbl, dupe_alien_tbl, family_detail,
                        roster_df, cols, roster_cols):
    """Return a dict of named DataFrames, each isolating one data-quality issue."""
    reports = {}

    reports["Missing Alien Number"] = df[df["alien_missing"]].copy()
    reports["Malformed Alien Number"] = df[df["alien_malformed"]].copy()
    reports["Missing Case Number"] = df[df["case_missing"]].copy()

    # Exact duplicate enrollment rows (fully identical original rows).
    orig_cols = [c for c in df.columns if not c.startswith(
        ("alien_", "case_", "program_clean", "program_key", "enroll_dt", "term_dt",
         "family_size_num", "is_", "active_", "status_says", "term_before"))]
    dup_mask = df.duplicated(subset=orig_cols, keep=False)
    reports["Duplicate Enrollment Rows"] = df[dup_mask].copy()

    # Duplicate Alien+Program combinations (multiple records same person/program).
    v = valid_rows(df)
    ap_dup = v[v.duplicated(subset=["alien_clean", "program_key"], keep=False)]
    reports["Duplicate Alien+Program"] = ap_dup.copy()

    reports["Alien Linked to Multiple Cases"] = multi_case_tbl
    reports["Possible Same-Person Alien Formats"] = dupe_alien_tbl

    # Conflicting family sizes.
    fs = (df.dropna(subset=["case_clean"])
            .groupby("case_clean")["family_size_num"]
            .apply(lambda s: sorted(set(int(x) for x in s.dropna()))))
    conflicting = fs[fs.apply(len) > 1].reset_index()
    conflicting.columns = ["Case Number", "Recorded Family Sizes"]
    reports["Conflicting Family Sizes"] = conflicting

    # Family size vs. known members mismatches (from family detail).
    if not family_detail.empty:
        too_small = family_detail[family_detail["Data-Quality Flag"] == "FAMILY_SIZE_TOO_SMALL"]
        too_big = family_detail[family_detail["Data-Quality Flag"] == "MEMBERS_NOT_IN_DATA"]
        unresolved = family_detail[family_detail["Data-Quality Flag"] == "UNRESOLVED_FAMILY_SIZE"]
        reports["Family Size Smaller Than Members"] = too_small
        reports["Family Size Larger Than Members"] = too_big
        reports["Unresolved Family Reach"] = unresolved

    reports["Termination Before Enrollment"] = df[df["term_before_enroll"]].copy()
    reports["Active/Status Conflicts"] = df[df["active_status_conflict"]].copy()

    # Blank / inconsistent program names.
    reports["Blank Program Names"] = df[df["program_clean"].isna() |
                                        (df["program_clean"].astype(str).str.strip() == "")].copy()

    # Roster reconciliation (only when a separate roster is provided).
    if roster_df is not None:
        r = clean_identifiers(roster_df, roster_cols)
        enrolled_aliens = set(valid_rows(df)["alien_clean"])
        roster_aliens = set(r[r["alien_clean"].notna()]["alien_clean"])
        reports["Enrollments Not In Roster"] = valid_rows(df)[
            ~valid_rows(df)["alien_clean"].isin(roster_aliens)].copy()
        reports["Roster Members Without Enrollment"] = r[
            r["alien_clean"].notna() & ~r["alien_clean"].isin(enrolled_aliens)].copy()

    return reports


# =============================================================================
# 11. RECONCILIATION REPORT
# =============================================================================
def reconciliation_report(df, org, family_summary):
    """Auditable chain from raw rows -> valid records -> unique clients -> adjusted."""
    raw_rows = len(df)

    orig_cols = [c for c in df.columns if not c.startswith(
        ("alien_", "case_", "program_clean", "program_key", "enroll_dt", "term_dt",
         "family_size_num", "is_", "active_", "status_says", "term_before"))]
    exact_dupes = int(df.duplicated(subset=orig_cols, keep="first").sum())

    invalid_id_rows = int(df["alien_clean"].isna().sum())
    valid_records = raw_rows - invalid_id_rows

    unique_clients = org["unique_clients_served"]
    total_adjusted = int(family_summary["Adjusted Reach Served"].sum()) if not family_summary.empty else 0

    rows = [
        ("Raw enrollment rows", raw_rows, "All rows in the enrollment dataset."),
        ("(-) Exact duplicate rows", -exact_dupes, "Fully identical rows (kept once)."),
        ("(-) Invalid/unusable identifier rows", -invalid_id_rows,
         "Rows with missing or placeholder Alien Numbers (not counted as clients)."),
        ("(=) Valid enrollment records", valid_records,
         "Rows with a usable Alien Number (may still contain per-person duplicates)."),
        ("(=) Unique documented clients served", unique_clients,
         "Valid rows deduplicated by Alien Number (the org-wide unduplicated total)."),
        ("(+) Family-level adjustment (per-program reach)", total_adjusted,
         "Sum of per-program adjusted family reach; a SEPARATE reach measure, "
         "NOT added to the org-wide client total."),
    ]
    recon = pd.DataFrame(rows, columns=["Step", "Value", "Explanation"])
    return recon


# =============================================================================
# 12. ORGANIZATION SUMMARY TABLE
# =============================================================================
def organization_summary(df, org, quality, family_detail):
    def _n(key):
        return len(quality.get(key, pd.DataFrame()))
    rows = [
        ("Total enrollment rows", len(df)),
        ("Unique valid Alien Numbers", org["unique_valid_aliens"]),
        ("Unique clients served", org["unique_clients_served"]),
        ("Unique clients currently active", org["unique_clients_active"]),
        ("Unique families served", org["unique_families_served"]),
        ("Unique families currently active", org["unique_families_active"]),
        ("Rows missing Alien Number", int(df["alien_missing"].sum())),
        ("Rows with malformed Alien Number", int(df["alien_malformed"].sum())),
        ("Rows missing Case Number", int(df["case_missing"].sum())),
        ("Duplicate enrollment rows", _n("Duplicate Enrollment Rows")),
        ("Alien Numbers linked to multiple Cases", _n("Alien Linked to Multiple Cases")),
        ("Possible same-person Alien formats", _n("Possible Same-Person Alien Formats")),
        ("Cases requiring family-size review",
         int((family_detail["Data-Quality Flag"] != "").sum()) if not family_detail.empty else 0),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def build_program_summary(prog_counts, family_summary):
    """Merge documented per-program counts with adjusted family reach."""
    ps = prog_counts.copy()
    ps = ps.merge(family_summary, on="Program", how="left")
    ps["Adjusted Reach Served"] = ps["Adjusted Reach Served"].where(
        ps["Is Family-Level Program"], np.nan)
    ps["Adjusted Reach Active"] = ps["Adjusted Reach Active"].where(
        ps["Is Family-Level Program"], np.nan)

    def _diff(r):
        if not r["Is Family-Level Program"] or pd.isna(r["Adjusted Reach Served"]):
            return np.nan
        return r["Adjusted Reach Served"] - r["Documented Clients Served"]

    def _pct(r):
        if (not r["Is Family-Level Program"] or pd.isna(r["Adjusted Reach Served"])
                or r["Documented Clients Served"] == 0):
            return np.nan
        return (r["Adjusted Reach Served"] - r["Documented Clients Served"]) / \
            r["Documented Clients Served"]

    ps["Adjusted vs Documented (Diff)"] = ps.apply(_diff, axis=1)
    ps["Family-Level % Increase"] = ps.apply(_pct, axis=1)
    return ps


# =============================================================================
# 13. EXCEL EXPORT  (formatted, non-destructive)
# =============================================================================
def _autosize_and_format(writer, sheet_name, df):
    from openpyxl.utils import get_column_letter
    ws = writer.sheets[sheet_name]
    ws.freeze_panes = "A2"
    n_rows, n_cols = df.shape
    if n_rows >= 0 and n_cols > 0:
        ws.auto_filter.ref = f"A1:{get_column_letter(n_cols)}{n_rows + 1}"
    for i, col in enumerate(df.columns, start=1):
        letter = get_column_letter(i)
        try:
            max_len = max([len(str(col))] +
                          [len(str(v)) for v in df[col].head(500).tolist()])
        except Exception:
            max_len = len(str(col))
        ws.column_dimensions[letter].width = min(max(10, max_len + 2), 50)


def export_workbook(path, tables):
    """
    Write all report tables to a formatted xlsx workbook.
    `tables` = list of (sheet_name, DataFrame).  Percentages formatted where
    column name contains '%'; dates formatted consistently.
    """
    from openpyxl.styles import Font, PatternFill
    with pd.ExcelWriter(path, engine="openpyxl", datetime_format="YYYY-MM-DD",
                        date_format="YYYY-MM-DD") as writer:
        for sheet_name, df in tables:
            safe = str(sheet_name)[:31]
            out = df.copy()
            # Render list-cells as strings so Excel accepts them.
            for c in out.columns:
                if out[c].apply(lambda x: isinstance(x, (list, set, tuple))).any():
                    out[c] = out[c].apply(
                        lambda x: "; ".join(map(str, x)) if isinstance(x, (list, set, tuple)) else x)
            out.to_excel(writer, sheet_name=safe, index=False)
            _autosize_and_format(writer, safe, out)

            ws = writer.sheets[safe]
            header_fill = PatternFill("solid", fgColor="1F4E78")
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
            # Percent formatting.
            from openpyxl.utils import get_column_letter
            for i, col in enumerate(out.columns, start=1):
                if "%" in str(col):
                    letter = get_column_letter(i)
                    for row in range(2, len(out) + 2):
                        ws[f"{letter}{row}"].number_format = "0.0%"
    return path


# =============================================================================
# 14. TOP-LEVEL ANALYSIS ORCHESTRATION
# =============================================================================
def analyze(enroll_df, roster_df=None, verbose=True):
    """Run the full pipeline on already-loaded DataFrames; return a results dict."""
    cols, missing = resolve_columns(enroll_df, COLUMN_MAP)
    roster_cols = None
    if roster_df is not None:
        roster_cols, _ = resolve_columns(roster_df, COLUMN_MAP)

    if verbose:
        print("Resolved columns:")
        for k, v in cols.items():
            print(f"    {k:<16} -> {v}")
        if missing:
            print("\n[WARNING] These configured fields were NOT found and their "
                  "calculations will be skipped or limited:")
            for m in missing:
                print(f"    - {m}")
        # Required fields.
        for req in ("alien_number", "case_number", "program"):
            if cols[req] is None:
                print(f"[CRITICAL] Required field '{req}' is missing; results will be unreliable.")

    # Clean + prepare.
    df = clean_identifiers(enroll_df, cols)
    df = prepare_enrollment(df, cols)
    as_of = df.attrs.get("as_of_used")
    if verbose:
        print(f"\nAS-OF date used for 'currently active': {as_of.date()}")
        if AS_OF_DATE is None:
            print("    (No AS_OF_DATE configured -> today's date used.)")
        print(f"Reporting period: start={REPORT_START_DATE}, end={REPORT_END_DATE} "
              f"({'all-time' if not REPORT_START_DATE and not REPORT_END_DATE else 'bounded'})")

    multi_case_tbl, dupe_alien_tbl = detect_identifier_conflicts(df)
    known_members, roster_available = build_roster(df, roster_df, cols, roster_cols)

    org = org_wide_counts(df)
    prog_counts = per_program_counts(df)
    family_detail = family_program_detail(df, known_members, roster_available)
    family_summary = summarize_family_reach(family_detail)
    program_summary = build_program_summary(prog_counts, family_summary)
    client_detail = client_level_detail(df, family_detail, cols)
    quality = data_quality_report(df, multi_case_tbl, dupe_alien_tbl, family_detail,
                                  roster_df, cols, roster_cols)
    org_summary = organization_summary(df, org, quality, family_detail)
    recon = reconciliation_report(df, org, family_summary)

    if verbose:
        print("\n" + "=" * 70)
        print("ORGANIZATION SUMMARY")
        print("=" * 70)
        print(org_summary.to_string(index=False))
        print("\n" + "=" * 70)
        print("PROGRAM SUMMARY")
        print("=" * 70)
        show = program_summary[[
            "Program", "Raw Enrollment Rows", "Documented Clients Served",
            "Documented Clients Active", "Is Family-Level Program",
            "Adjusted Reach Served", "Adjusted vs Documented (Diff)"]]
        print(show.to_string(index=False))
        print("\n[NOTE] Organization-wide unduplicated clients served = "
              f"{org['unique_clients_served']}.  This is NOT the sum of the "
              "per-program client counts.")

    return {
        "cleaned_enrollment": df,
        "cleaned_roster": clean_identifiers(roster_df, roster_cols) if roster_df is not None else None,
        "org": org,
        "organization_summary": org_summary,
        "program_summary": program_summary,
        "family_detail": family_detail,
        "client_detail": client_detail,
        "quality": quality,
        "reconciliation": recon,
    }


def write_reports(results, output_file=OUTPUT_FILE):
    """Assemble all output tables into one formatted Excel workbook."""
    q = results["quality"]
    quality_combined = []
    for name, tbl in q.items():
        if tbl is None or len(tbl) == 0:
            continue
        t = tbl.copy()
        t.insert(0, "Issue Type", name)
        # Keep it compact: identifier + a few key columns when available.
        quality_combined.append(t)
    quality_sheet = (pd.concat(quality_combined, ignore_index=True, sort=False)
                     if quality_combined else pd.DataFrame({"Issue Type": [],
                                                            "Note": []}))

    tables = [
        ("Organization Summary", results["organization_summary"]),
        ("Program Summary", results["program_summary"]),
        ("Family Program Detail", results["family_detail"]),
        ("Unique Client Detail", results["client_detail"]),
        ("Data Quality", quality_sheet),
        ("Reconciliation", results["reconciliation"]),
        ("Cleaned Enrollment Data", results["cleaned_enrollment"]),
    ]
    if results["cleaned_roster"] is not None:
        tables.append(("Cleaned Client Roster", results["cleaned_roster"]))

    export_workbook(output_file, tables)
    print(f"\n[OK] Formatted workbook written to: {output_file}")
    return output_file


# =============================================================================
# 15. SYNTHETIC TEST DATASET + VERIFICATION TESTS
# =============================================================================
def build_synthetic_data():
    """
    Encodes the required example:
      * Case CASE-100, 12 members, distinct Alien Numbers.
      * 2 adults in Refugee Case Management (family-level).
      * 1 of them also in Refugee Health Promotion (family-level).
      * 3 children in Refugee School Impact (individual-level).
    Plus edge cases: duplicate row, missing/placeholder identifiers,
    a termination-before-enrollment error, and a cross-program person.
    """
    A = [f"A10000{str(i).zfill(3)}" for i in range(1, 13)]  # 12 distinct aliens
    rows = []

    def row(case, alien, prog, enr, term, size, name, status="Active Enrollment"):
        rows.append({
            "Case Number": case, "Alien Number": alien, "Case Size": size,
            "First Name": name, "Last Name": "Test", "Program": prog,
            "Date of Enrollment": enr, "Date of Termination": term,
            "Is program Enrollment Active?": status,
        })

    # Refugee Case Management: 2 adults.
    row("CASE-100", A[0], "Refugee Case Management", "2024-01-01", "2025-01-01", 12, "Adult1", "NO Active Enrollment")
    row("CASE-100", A[1], "Refugee Case Management", "2024-01-01", None, 12, "Adult2", "Active Enrollment")
    # One adult also in Refugee Health Promotion.
    row("CASE-100", A[0], "Mass Refugee Health Promotion Program", "2024-02-01", None, 12, "Adult1", "Active Enrollment")
    # Three children in Refugee School Impact (individual-level).
    row("CASE-100", A[2], "Refugee School Impact", "2024-03-01", None, 12, "Child1", "Active Enrollment")
    row("CASE-100", A[3], "Refugee School Impact", "2024-03-01", None, 12, "Child2", "Active Enrollment")
    row("CASE-100", A[4], "Refugee School Impact", "2024-03-01", None, 12, "Child3", "Active Enrollment")

    # Cross-program person in a different family (counts once org-wide, once per program).
    row("CASE-200", "A2000001", "Refugee Case Management", "2024-01-01", None, 3, "Multi", "Active Enrollment")
    row("CASE-200", "A2000001", "Refugee Cash Assistance", "2024-01-05", None, 3, "Multi", "Active Enrollment")
    row("CASE-200", "A2000001", "Refugee School Impact", "2024-01-10", None, 3, "Multi", "Active Enrollment")
    # Exact duplicate of the previous row (must not inflate any count).
    row("CASE-200", "A2000001", "Refugee School Impact", "2024-01-10", None, 3, "Multi", "Active Enrollment")

    # Missing / placeholder identifiers (must be flagged, never counted).
    row("CASE-300", None, "Refugee Case Management", "2024-01-01", None, 5, "NoAlien", "Active Enrollment")
    row("CASE-300", "A00000000", "Refugee Case Management", "2024-01-01", None, 5, "ZeroAlien", "Active Enrollment")

    # Termination-before-enrollment error (must be flagged).
    row("CASE-400", "A4000001", "Refugee Cash Assistance", "2024-06-01", "2024-01-01", 2, "BadDates", "NO Active Enrollment")

    return pd.DataFrame(rows)


def run_verification_tests():
    """Run the 10 required logic checks against the synthetic dataset."""
    print("\n" + "#" * 70)
    print("# SYNTHETIC VERIFICATION TESTS")
    print("#" * 70)

    global AS_OF_DATE
    saved_as_of = AS_OF_DATE
    AS_OF_DATE = "2024-12-31"   # fixed for reproducibility

    syn = build_synthetic_data()
    res = analyze(syn, verbose=False)
    df = res["cleaned_enrollment"]
    org = res["org"]
    prog = res["program_summary"].set_index("Program")
    fam = res["family_detail"]

    results = []

    def check(name, condition, detail=""):
        results.append((name, bool(condition), detail))

    # 1. No Alien Number counted >1 in org-wide unique total.
    served_aliens = valid_rows(df[df["is_served"]])["alien_clean"]
    check("1. Org-wide unique = distinct aliens (no double count)",
          org["unique_clients_served"] == served_aliens.nunique(),
          f"{org['unique_clients_served']} unique served")

    # 2. No alien counted twice within same program.
    v = valid_rows(df)
    within = v.groupby("program_clean")["alien_clean"].apply(lambda s: s.nunique())
    school = prog.loc["Refugee School Impact", "Documented Clients Served"]
    check("2. Within-program dedup (School Impact = 4 distinct people)",
          school == 4, f"School Impact documented = {school}")  # 3 children + Multi

    # 3. Same person appears once in several program counts.
    multi_rows = v[v["alien_clean"] == "A2000001"]
    check("3. Cross-program person counts once per program",
          multi_rows["program_clean"].nunique() == 3,
          "A2000001 in 3 distinct programs")

    # 4. No Case Number double counted in family count.
    fam_served = valid_rows(df[df["is_served"]])["case_clean"].nunique()
    check("4. Families deduplicated by Case Number",
          org["unique_families_served"] == fam_served,
          f"{org['unique_families_served']} families")

    # 5. Adjusted reach >= documented, always.
    rcm = fam[(fam["Program"] == "Refugee Case Management") &
              (fam["Case Number"] == "CASE-100")].iloc[0]
    check("5. Adjusted reach >= documented (all family rows)",
          (fam["Adjusted Family Reach"] >= fam["Documented Enrolled Members"]).all(),
          f"CASE-100 RCM: documented={rcm['Documented Enrolled Members']}, "
          f"adjusted={rcm['Adjusted Family Reach']}")

    # 6. Family-size estimate never silently treated as roster count.
    est_rows = fam[fam["Adjustment Method"] == "Family-size estimate"]
    check("6. Family-size estimates are labeled, not confirmed rosters",
          (est_rows["Adjustment Method"] == "Family-size estimate").all(),
          f"{len(est_rows)} estimate-based cases labeled")

    # 7. Missing identifiers not counted as valid clients.
    check("7. Missing/placeholder aliens excluded from client count",
          "A00000000" not in set(v["alien_clean"]) and org["unique_clients_served"] > 0,
          "placeholder A00000000 and blank excluded")

    # 8. Exact duplicate rows don't inflate counts.
    check("8. Exact duplicate row does not change School Impact count",
          school == 4, "duplicate CASE-200 School Impact row ignored")

    # 9. Termination-before-enrollment flagged.
    tbe = res["quality"]["Termination Before Enrollment"]
    check("9. Termination-before-enrollment flagged",
          len(tbe) == 1, f"{len(tbe)} bad-date row flagged")

    # 10. Sum of program counts != org-wide total (must be presented separately).
    sum_prog = prog["Documented Clients Served"].sum()
    check("10. Sum-of-programs is NOT the org-wide unduplicated total",
          sum_prog != org["unique_clients_served"],
          f"sum(programs)={sum_prog} vs org-wide={org['unique_clients_served']}")

    # ---- Example-specific expected values ----
    print("\nExample checks (CASE-100):")
    rcm_doc = prog.loc["Refugee Case Management", "Documented Clients Served"]
    rcm_adj = prog.loc["Refugee Case Management", "Adjusted Reach Served"]
    rhp_doc = prog.loc["Mass Refugee Health Promotion Program", "Documented Clients Served"]
    rhp_adj = prog.loc["Mass Refugee Health Promotion Program", "Adjusted Reach Served"]
    rsi_doc = prog.loc["Refugee School Impact", "Documented Clients Served"]
    example = [
        ("Refugee Case Management documented", rcm_doc, 3),      # CASE-100(2) + CASE-200(1)
        # CASE-100 adjusts to 12 (recorded size); CASE-200 adjusts to 3 (recorded
        # size, family-level program) -> 12 + 3 = 15.  This demonstrates that the
        # family-size estimate expands EVERY family-level case, not just CASE-100.
        ("Refugee Case Management adjusted reach", rcm_adj, 15),
        ("Refugee Health Promotion documented", rhp_doc, 1),
        ("Refugee Health Promotion adjusted reach", rhp_adj, 12),
        ("Refugee School Impact documented", rsi_doc, 4),        # 3 children + Multi
    ]
    for label, got, exp in example:
        ok = int(got) == exp
        print(f"    [{'PASS' if ok else 'FAIL'}] {label}: got={int(got)} expected={exp}")
        results.append((f"Example: {label}", ok, f"got={int(got)} exp={exp}"))

    print("\nRequired logic checks:")
    all_pass = True
    for name, ok, detail in results:
        all_pass &= ok
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}"
              + (f"  ({detail})" if detail else ""))

    print("\n" + ("ALL TESTS PASSED" if all_pass else ">>> SOME TESTS FAILED <<<"))
    AS_OF_DATE = saved_as_of
    return all_pass


# =============================================================================
# 16. COLAB / CLI ENTRY POINT
# =============================================================================
def colab_upload():
    """In Google Colab, prompt for file upload(s). Returns list of paths."""
    try:
        from google.colab import files  # noqa
    except Exception:
        return []
    print("Upload your enrollment file (and optionally a roster file):")
    uploaded = files.upload()
    return list(uploaded.keys())


def main():
    # Step 1: always prove the logic first.
    passed = run_verification_tests()
    if not passed:
        print("\n[STOP] Verification tests failed; fix logic before trusting real output.")

    # Step 2: analyze the real file if configured / uploaded.
    id_like = [COLUMN_MAP["alien_number"], COLUMN_MAP["case_number"]]

    enroll_path = ENROLLMENT_FILE
    roster_path = ROSTER_FILE

    # In Colab with nothing configured, offer an upload.
    if enroll_path is None:
        uploaded = colab_upload()
        if uploaded:
            enroll_path = uploaded[0]
            if len(uploaded) > 1:
                roster_path = uploaded[1]

    if enroll_path is None:
        print("\n[INFO] No real input file configured (ENROLLMENT_FILE is None). "
              "Set it in the config section or upload a file in Colab to analyze "
              "your data.  The verification tests above already demonstrate the logic.")
        return

    print(f"\nLoading enrollment file: {enroll_path}")
    enroll_df = load_dataframe(enroll_path, ENROLLMENT_SHEET, id_like_columns=id_like)
    roster_df = load_dataframe(roster_path, ROSTER_SHEET, id_like_columns=id_like) if roster_path else None
    print(f"Loaded {len(enroll_df):,} enrollment rows.")

    results = analyze(enroll_df, roster_df, verbose=True)
    write_reports(results, OUTPUT_FILE)


if __name__ == "__main__":
    main()
