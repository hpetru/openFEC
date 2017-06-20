drop materialized view if exists ofec_entity_chart_mv_tmp;
create materialized view ofec_entity_chart_mv_tmp as
-- candidates
with cand_totals as (
    select
        'candidate'::text as type,
        extract(month from coverage_end_date) as month,
        extract(year from coverage_end_date) as year,
        sum(coalesce(receipts,0) -
            (
                coalesce(political_party_committee_contributions,0) +
                coalesce(other_political_committee_contributions,0) +
                coalesce(offsets_to_operating_expenditures,0) +
                coalesce(loan_repayments,0) +
                coalesce(contribution_refunds,0)
            )
        ) as candidate_adjusted_total_receipts,
        sum(coalesce(disbursements, 0) -
            (
                coalesce(transfers_to_other_authorized_committee,0) +
                coalesce(loan_repayments,0) +
                coalesce(contribution_refunds,0) +
                coalesce(other_disbursements,0)
            )
        ) as candidate_adjusted_total_disbursements
    from
        ofec_totals_house_senate_mv_tmp
    where
        cycle >= 2008
    group by
        month,
        year
),
-- PACs
pac_totals as (
    select
        'pac'::text as type,
        extract(month from coverage_end_date) as month,
        extract(year from coverage_end_date) as year,
        sum(coalesce(receipts, 0) -
            (
                -- contributions from political party committees and other political committees
                coalesce(political_party_committee_contributions,0) +
                -- contributions from political party committees and other political committees
                coalesce(other_political_committee_contributions,0) +
                -- offsets to operating expenditures
                coalesce(offsets_to_operating_expenditures,0) +
                -- Contribution refunds going out
                coalesce(fed_candidate_contribution_refunds,0) +
                -- Transfers from nonfederal accounts for allocated activities
                coalesce(transfers_from_nonfed_account,0) +
                -- loan repayments
                --coalesce(loan_repymts_received_per,0) +
                coalesce(loan_repayments_other_loans, 0) +
                -- contribution refunds
                coalesce(contribution_refunds,0)
            )
        ) as pac_adjusted_total_receipts,
        sum(coalesce(disbursements,0) -
            (
                -- Nonfederal share of allocated disbursements
                coalesce(shared_nonfed_operating_expenditures,0) +
                -- Transfers to other authorized committees and affiliated committees
                coalesce(transfers_to_affiliated_committee,0) +
                -- Contributions to candidates and other political committees
                coalesce(fed_candidate_committee_contributions,0) +
                -- Loan repayments
                coalesce(loan_repayments_other_loans,0) +
                -- Contribution refunds
                coalesce(contribution_refunds,0) +
                -- Other disbursements
                coalesce(other_disbursements,0)
            )
        ) as pac_adjusted_total_disbursements
    from ofec_totals_pacs_mv_tmp
    where
        committee_type in ('N', 'Q', 'O', 'V', 'W')
        and designation <> 'J'
        and cycle >= 2008
    group by
        month,
        year
),
-- Parties
party_totals as (
    select
        'party'::text as type,
        extract(month from coverage_end_date) as month,
        extract(year from coverage_end_date) as year,
        sum(coalesce(receipts, 0) -
            (
                coalesce(political_party_committee_contributions,0) +
                coalesce(other_political_committee_contributions,0) +
                coalesce(offsets_to_operating_expenditures,0) +
                coalesce(fed_candidate_contribution_refunds,0) +
                coalesce(transfers_from_nonfed_account,0) +
                -- this was already commented out, want to confirm this
                -- coalesce(loan_repymts_received_per,0) +
                coalesce(loan_repayments_other_loans, 0) +
                coalesce(contribution_refunds,0)
            )
        ) as party_adjusted_total_receipts,
        sum(coalesce(disbursements,0) -
            (
                coalesce(shared_nonfed_operating_expenditures,0) +
                -- confirm var
                coalesce(transfers_to_other_authorized_committee,0) +
                -- coalesce(tranf_to_other_auth_cmte,0) +
                coalesce(fed_candidate_committee_contributions,0) +
                coalesce(loan_repayments_other_loans,0) +
                coalesce(contribution_refunds,0) +
                coalesce(other_disbursements,0)
            )
        ) as party_adjusted_total_disbursements
    from ofec_totals_parties_mv_tmp
    where
        committee_type in ('X', 'Y')
        and designation <> 'J'
        -- excluding host conventions because they have different rules than party committees
        and committee_id not in ('C00578419', 'C00485110', 'C00422048', 'C00567057', 'C00483586', 'C00431791', 'C00571133',
            'C00500405', 'C00435560', 'C00572958', 'C00493254', 'C00496570', 'C00431593')
        and cycle >= 2008
    group by
        month,
        year
),
communication_totals as (
  select
    get_cycle(rpt_yr) as cycle,
    f.rpt_yr as year,
    extract(month from to_date(cast(cvg_end_dt as text), 'YYYY-MM-DD')) as month,
    sum(coalesce(ttl_communication_cost ,0)) as comms_totals
  from public.fec_vsum_f7_vw f
  where rpt_yr >= 2007
  and most_recent_filing_flag = 'Y'
  group by get_cycle(rpt_yr), f.rpt_yr, extract(month from to_date(cast(cvg_end_dt as text), 'YYYY-MM-DD'))
),
electioneering_totals as (
  select
    get_cycle(rpt_yr) as cycle,
    f.rpt_yr as year,
    extract(month from to_date(cast(end_cvg_dt as text), 'YYYY-MM-DD')) as month,
    sum(coalesce(ttl_dons_this_stmt ,0)) as total_donations_this_statement,
    sum(coalesce(ttl_disb_this_stmt ,0)) as total_disbursements_this_statement
  from public.fec_vsum_f9_vw f
  where rpt_yr >= 2007
  and most_recent_filing_flag = 'Y'
  group by get_cycle(rpt_yr), f.rpt_yr, extract(month from to_date(cast(end_cvg_dt as text), 'YYYY-MM-DD'))
  order by f.rpt_yr, extract(month from to_date(cast(end_cvg_dt as text), 'YYYY-MM-DD'))
),  -- merge
independent_expenditures as (
  select
    get_cycle(rpt_yr) as cycle,
    f.rpt_yr as year,
    extract(month from to_date(cast(cvg_end_dt as text), 'YYYY-MM-DD')) as month,
    sum(coalesce(ttl_indt_contb ,0)) as total_independent_contributions,
    sum(coalesce(ttl_indt_exp ,0)) as total_independent_expenditures
  from public.fec_vsum_f5_vw f
  where rpt_yr >= 2007
    and most_recent_filing_flag = 'Y'
  group by get_cycle(rpt_yr), f.rpt_yr, extract(month from to_date(cast(cvg_end_dt as text), 'YYYY-MM-DD'))
  ),
combined as (
    select
        month,
        year,
        year::numeric + (year::numeric % 2) as cycle,
        case when max(candidate_adjusted_total_receipts) is null
            then 0 else max(candidate_adjusted_total_receipts) end
        as candidate_receipts,
        case when max(cand_totals.candidate_adjusted_total_disbursements) is null
            then 0 else max(cand_totals.candidate_adjusted_total_disbursements) end
        as canidate_disbursements,
        case when max(pac_totals.pac_adjusted_total_receipts) is null
            then 0 else max(pac_totals.pac_adjusted_total_receipts) end
        as pac_receipts,
        case when max(pac_totals.pac_adjusted_total_disbursements) is null
            then 0 else max(pac_totals.pac_adjusted_total_disbursements) end
        as pac_disbursements,
        case when max(party_totals.party_adjusted_total_receipts) is null
            then 0 else max(party_totals.party_adjusted_total_receipts) end
        as party_receipts,
        case when max(party_totals.party_adjusted_total_disbursements) is null
            then 0 else max(party_totals.party_adjusted_total_disbursements) end
        as party_disbursements,
        case when max(communication_totals.comms_totals) is null
            then 0 else max(communication_totals.comms_totals) end
        as communications_totals,
        case when max(electioneering_totals.total_donations_this_statement) is null
            then 0 else max(electioneering_totals.total_donations_this_statement) end
        as electioneering_donations,
        case when max(electioneering_totals.total_disbursements_this_statement) is null
            then 0 else max(electioneering_totals.total_disbursements_this_statement) end
        as electioneering_disbursements,
        case when max(independent_expenditures.total_independent_contributions) is null
            then 0 else max(independent_expenditures.total_independent_contributions) end
        as independent_contributions,
        case when max(independent_expenditures.total_independent_expenditures) is null
            then 0 else max(independent_expenditures.total_independent_expenditures) end
        as independent_expenditures
    from cand_totals
    full outer join pac_totals using (month, year)
    full outer join party_totals using (month, year)
    full outer join communication_totals using (month, year)
    full outer join electioneering_totals using (month, year)
    full outer join independent_expenditures using (month, year)
    group by
        month,
        year
    order by year, month
)
select
    row_number() over () as idx,
    month,
    year,
    cycle,
    last_day_of_month(make_timestamp(cast(year as int), cast(month as int), 1, 0, 0, 0.0)) as date,
    sum(candidate_receipts) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_candidate_receipts,
    candidate_receipts,
    sum(canidate_disbursements) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_candidate_disbursements,
    canidate_disbursements,
    sum(pac_receipts) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_pac_receipts,
    pac_receipts,
    sum(pac_disbursements) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_pac_disbursements,
    pac_disbursements,
    sum(party_receipts) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_party_receipts,
    party_receipts,
    sum(party_disbursements) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_party_disbursements,
    party_disbursements,
    sum(communications_totals) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_communication_totals,
    communications_totals,
    sum(electioneering_donations) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_electioneering_donations,
    electioneering_donations,
    sum(electioneering_disbursements) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_electioneering_disbursements,
    electioneering_disbursements,
    sum(independent_contributions) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_independent_contributions,
    independent_contributions,
    sum(independent_expenditures) OVER (PARTITION BY cycle order by year asc, month asc) as cumulative_independent_expenditures,
    independent_expenditures

from combined
where cycle >= 2008
;

create unique index on ofec_entity_chart_mv_tmp (idx);
create index on ofec_entity_chart_mv_tmp (cycle);
