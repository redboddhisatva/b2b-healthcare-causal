import numpy as np
import pandas as pd
import statsmodels.api as sm


def add_relative_month(df):
    """
    Adds a 'rel_month' column indicating the number of months relative to
    the first trial kit delivery for each clinic:
      - 0: The exact month the clinic received the trial kit
      - -1: One month before trial delivery
      - +2: Two months after trial delivery
      - NaN: Never-treated control clinics that never received a trial kit
    """
    df = df.copy()
    m_dt = pd.to_datetime(df['month'])
    t_dt = pd.to_datetime(df['first_trial_month'])
    df['rel_month'] = (m_dt.dt.year - t_dt.dt.year) * 12 + (m_dt.dt.month - t_dt.dt.month)
    return df


def check_balanced_panel(df, expected_months=36):
    """
    Checks that every clinic in the dataset has exactly all expected months (36 months).
    
    Why this matters:
    The demeaning trick in run_simple_twfe (subtracting clinic mean and month mean)
    is mathematically identical to full Two-Way Fixed Effects (TWFE) with dummy
    variables ONLY when the panel is balanced (every clinic has all months).
    If rows are dropped, the panel becomes unbalanced and requires iterative methods.
    Therefore, never drop rows from the panel before running TWFE.
    """
    counts = df.groupby('clinic_id')['month'].nunique()
    if not (counts == expected_months).all():
        unbalanced = counts[counts != expected_months]
        raise ValueError(
            f"Panel is not balanced! {len(unbalanced)} clinics do not have {expected_months} months."
        )
    return True


def run_simple_twfe(data, outcome_col, treatment_cols):
    """
    Two-Way Fixed Effects (TWFE) DiD regression in plain pandas.
    - Clinic fixed effect: each clinic is compared only with its own average
      (big hospital is never compared raw with a small optical shop).
    - Month fixed effect: removes things that hit ALL clinics in the same month
      (seasonality like hay-fever season, market-wide growth).
    Trick: subtract the clinic average and the month average, add back the overall average.
    This equals adding clinic + month dummies, BUT ONLY on a balanced panel
    (every clinic has every month). Call check_balanced_panel() first.
    Standard errors are clustered by clinic (same clinic's months are not independent).
    """
    if isinstance(treatment_cols, str):
        treatment_cols = [treatment_cols]
    d = data.copy()

    def adjust(col):
        return (d[col]
                - d.groupby('clinic_id')[col].transform('mean')
                - d.groupby('month')[col].transform('mean')
                + d[col].mean())

    y = adjust(outcome_col)
    X = pd.concat({c: adjust(c) for c in treatment_cols}, axis=1)

    model = sm.OLS(y, X).fit(cov_type='cluster', cov_kwds={'groups': d['clinic_id']})
    first = treatment_cols[0]
    return model.params[first], model.bse[first], model.pvalues[first]
