# Future-Agent Analysis Reference

This note summarizes the exploratory economic analysis performed in this repository so future agents can reproduce, audit, and extend it without rereading the original conversation.

## Data Fetching Rule

Any downloaded data must come through a repeatable Python fetcher in the repo's data pipeline.

- Do not fetch source data with `curl`, browser downloads, ad hoc shell commands, or one-off scripts.
- New data may be requested when needed, but the implementation must add or update a Python fetcher first.
- Raw files should be written under `data/raw/<source>/`.
- Normalized outputs should be written under `data/processed/<dataset>/`.
- Metadata sidecars should document source URL, fetch time, raw paths, frequency, units, and method.
- If a missing data file is discovered, update the fetcher and tests, then regenerate outputs through the pipeline.

Audit note: `data/raw/bls/cex/cx.data.1.AllData` was manually downloaded during exploration to finish the debt chart. Treat that file as non-repeatable until it is incorporated into the CEX Python fetcher. It should not be used as precedent for future work.

## Investigation Summary

The work built a set of chart/table artifacts around U.S. labor, GDP expenditure components, consumer spending, and household distributional measures.

- Labor market: charted labor force size, participation rate, unemployment, and unemployment rate from 2016 to 2025 using BLS CPS data.
- Labor vs macro activity: aligned monthly labor and PCE data to quarterly averages, joined them with BEA GDP, and computed correlations.
- GDP components: indexed expenditure-side GDP components from 2016Q1 and added total GDP from the expenditure identity.
- CEX consumption: indexed aggregate annual consumer expenditure by income quintile from 2016 to 2024.
- CEX saving-rate proxy: computed a quintile-level proxy from aggregate after-tax income and aggregate expenditures, available through 2023.
- CEX debt: charted non-mortgage debt per consumer unit by income quintile, using credit-card, student-loan, and other-loan amounts owed.

## Data Inventory

General:

- search in `data/` for available datasets
- store outputs in `outputs/`

Core processed datasets used:

- `data/processed/bls_labor/bls_labor.csv`: monthly BLS labor series. October 2025 is missing for the core CPS measures in the local data.
- `data/processed/bls_oews_swe_employment/bls_oews_swe_employment.csv`: annual BLS OEWS all-occupations employment and harmonized software-developer employment.
- `data/processed/bea_pce/bea_pce.csv`: monthly BEA PCE series.
- `data/processed/bea_gdp_components/bea_gdp_components.csv`: annual and quarterly BEA expenditure-side GDP components.
- `data/processed/bea_gdp_industry/bea_gdp_industry.csv`: quarterly BEA GDP-by-industry value added.
- `data/processed/bls_cex_consumption/bls_cex_consumption.csv`: normalized CEX aggregate spending by income quintile.
- `data/processed/scf_home_assets/scf_home_assets.csv`: SCF home and residential real-estate assets by household groups.
- `data/processed/acs_major_employment/acs_major_employment.csv`: national ACS PUMS employment-to-population rates by bachelor's field of degree for recent graduates ages 22-27, 2015-2024. The 2020 observation uses Census experimental ACS 1-year PUMS.
- `data/processed/fred_swe_labor_market/fred_swe_labor_market.csv`: FRED software-developer employment, broader computer/math employment proxy, and Indeed job-postings indexes.
- `data/processed/fred_indeed_job_postings/fred_indeed_job_postings.csv`: FRED/Indeed current job-postings indexes for all active U.S. sector/occupation series and selected states (MA, NJ, NY, CA, WA, TX, FL).
- `data/processed/fred_consumer_sentiment/fred_consumer_sentiment.csv`: monthly University of Michigan consumer sentiment index from FRED.
- `data/processed/fred_oil_energy_prices/fred_oil_energy_prices.csv`: FRED WTI crude oil and U.S. regular gasoline prices for oil-price scenario modeling.

Generated artifacts:

- `outputs/labor_market_2016_2025.svg`
- `outputs/labor_pce_gdp_quarterly_2016_2025.csv`
- `outputs/labor_pce_gdp_correlations_2016_2025.csv`
- `outputs/labor_pce_gdp_correlation_2016_2025.svg`
- `outputs/gdp_components_index_2016_2025.csv`
- `outputs/gdp_components_index_2016_2025.svg`
- `outputs/cex_consumption_quintile_index_2016_2024.csv`
- `outputs/cex_consumption_quintile_index_2016_2024.svg`
- `outputs/cex_saving_rate_proxy_quintile_2016_2023.csv`
- `outputs/cex_saving_rate_proxy_quintile_2016_2023.svg`
- `outputs/cex_debt_quintile_2016_2024.csv`
- `outputs/cex_debt_quintile_2016_2024.svg`
- `outputs/consumer_sentiment_macro_comparison_2020_2025.csv`
- `outputs/oil_consumer_burden_scenarios.csv`

## Formula Notes

- GDP expenditure identity: `GDP = PCE + private investment + government + exports - imports`.
- GDP component index: each component is divided by its 2016Q1 value and multiplied by 100.
- CEX consumption index: each income quintile's aggregate annual expenditure is divided by its 2016 value and multiplied by 100.
- CEX saving-rate proxy: `(aggregate income after taxes - aggregate expenditures) / aggregate income after taxes`.
- CEX non-mortgage debt proxy: `credit-card debt + student-loan debt + other-loan debt` per consumer unit.
- ACS major employment rate: weighted employed recent graduates divided by weighted recent graduates in the same bachelor's field of degree. Recent graduates are ages 22-27 with a bachelor's degree or higher; employed ACS ESR codes are 1, 2, 4, and 5.
- Oil consumer-burden scenarios: annual WTI and gasoline prices estimate a linear oil-to-gasoline pass-through; latest common CEX/FRED year gasoline-and-other-fuels spending is scaled by scenario gasoline price while holding quantity fixed; burden is fuel spending divided by total annual expenditures.
- Oil supply-shock scenarios: net unresolved crude supply gaps are divided by baseline crude supply, then divided by the absolute value of short-run crude demand elasticity to estimate the WTI price-change share.

## Interpretation Notes

- PCE slightly outpaced current-dollar GDP from 2016Q1 to 2025Q4, but only by a small margin.
- Exports and imports grew more slowly than PCE and GDP, so trade declined as a share of GDP in the expenditure-component view.
- Government consumption and investment grew below GDP, while private investment nearly matched PCE.
- CEX aggregate spending growth by income quintile was surprisingly even from 2016 to 2024, with the highest quintile showing the lowest indexed growth among the quintiles.
- The CEX saving-rate proxy shows a large persistent level divide by quintile, not a large 2016-2023 divergence.
- Non-mortgage debt declined from 2023 to 2024 for the upper three quintiles, but rose for the lowest two quintiles.

## Caveats

- Many comparisons are nominal. Use real series before making purchasing-power or productivity claims.
- Oil consumer-burden scenarios are partial-equilibrium estimates; they do not model demand response, income feedback, GDP multipliers, or second-round inflation effects.
- Oil supply-shock scenarios treat the supply gap, baseline supply, and demand elasticity as assumptions, not fetched market-balance data.
- The CEX saving-rate proxy is not the official BEA/BLS distributional personal saving rate.
- CEX debt excludes mortgages, vehicle principal, and home-equity debt.
- CEX debt-to-after-tax-income stops at 2023 because the local CEX income-after-tax quintile series was not available for 2024.
- Imports are charted as positive import spending in the GDP component index, even though imports subtract from GDP.
- ACS major employment is a national employment-to-population measure, not a university placement rate or a NACE first-destination survey result.
- The Census Bureau did not release a standard 2020 ACS 1-year PUMS, so the decade-long ACS major-employment pipeline uses the experimental 2020 release for continuity.
- The exact FRED software-developer employment series stops at 2019; the current employment count in the FRED SWE labor-market dataset is a broader computer/math occupation proxy.
- FRED/Indeed job-postings data are copyrighted and require pre-approval for redistribution; use the normalized dataset for internal analysis with the same limitation.
- The BLS OEWS SWE employment series bridges a SOC code change: older years sum applications and systems software developers, while current years use the published Software Developers row when available.

## Recommended Next Steps

- Add `cx.data.1.AllData` to the CEX Python fetcher so debt analysis is fully repeatable.
- Add tests that verify the CEX fetcher retrieves all raw files required for consumption, saving proxy, and debt analysis.
- Consider adding official BEA/BLS distributional personal saving data for a true saving-rate-by-quintile series.
- Consider adding Fed Distributional Financial Accounts or SCF debt measures to validate CEX debt patterns against balance-sheet data.
