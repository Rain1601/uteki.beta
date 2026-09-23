"""Explicit material policy, separate from adoption/time eligibility gates."""
from datetime import date


def select_annual_context(eligible, company, material, documents):
    form = material.get('form')
    period = date.fromisoformat(material['period_end'])
    annual = form == '10-K' and material.get('company_id',company) == company and material.get('purpose') != 'hypothesis_validation'
    candidates, excluded = [], []
    for row in eligible:
        meta = documents.get(row['primary_document_id'], {})
        source_form = meta.get('form') or row.get('primary_form')
        source_period = meta.get('period_end') or row.get('primary_period_end')
        reason = None
        if source_form != '10-K' or meta.get('company_id',company) != company:
            reason = 'not_company_annual_baseline'
        elif not source_period:
            reason = 'unknown_baseline_period'
        else:
            try:
                source_date = date.fromisoformat(source_period)
                if (source_date >= period if annual else source_date > period) or row['primary_document_id'] == material.get('id'):
                    reason = 'not_prior_annual_period'
            except ValueError:
                reason = 'unknown_baseline_period'
        if reason:
            excluded.append({'snapshot_id':row['id'],'reason':reason})
        else:
            candidates.append((source_date,row))
    # Existing eligibility order resolves ties by source/run ordering, not an
    # arbitrary filesystem or insertion order. Only one baseline per fiscal year.
    candidates.sort(key=lambda pair:pair[0],reverse=True)
    selected, missing = [], []
    if annual:
        for year in (period.year-1,period.year-2):
            match=next((row for when,row in candidates if when.year == year),None)
            if match: selected.append(match)
            else: missing.append(year)
    elif candidates:
        selected=[candidates[0][1]]
    objective = 'annual_research' if annual else 'hypothesis_validation'
    policy = 'prior_two_fiscal_years_10k' if annual else 'latest_prior_10k'
    ids={r['id'] for r in selected}
    history=[row for _,row in candidates if row['id'] not in ids]
    return selected, history, excluded, {
        'policy_version':'annual-context-v1.2','context_policy':policy,'analysis_objective':objective,
        'missing_baseline_years':missing,'baseline_status':'ready' if selected and not missing else 'partial' if selected else 'missing',
        'analysis_instruction':('Compare prior two annual analyses with current evidence; preserve unknowns and assess hypothesis changes.' if annual else
            'Use the prior annual analysis as a hypothesis baseline. For each tested hypothesis report supported, weakened, contradicted or insufficient evidence, with citations. New hypotheses may be proposed, but must not silently replace the annual baseline.'),
        'baseline_is_hypothesis_not_fact':True,
    }
