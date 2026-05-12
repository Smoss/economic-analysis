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
- `data/processed/bea_pce/bea_pce.csv`: monthly BEA PCE series.
- `data/processed/bea_gdp_components/bea_gdp_components.csv`: annual and quarterly BEA expenditure-side GDP components.
- `data/processed/bea_gdp_industry/bea_gdp_industry.csv`: quarterly BEA GDP-by-industry value added.
- `data/processed/bls_cex_consumption/bls_cex_consumption.csv`: normalized CEX aggregate spending by income quintile.
- `data/processed/scf_home_assets/scf_home_assets.csv`: SCF home and residential real-estate assets by household groups.

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

## Formula Notes

- GDP expenditure identity: `GDP = PCE + private investment + government + exports - imports`.
- GDP component index: each component is divided by its 2016Q1 value and multiplied by 100.
- CEX consumption index: each income quintile's aggregate annual expenditure is divided by its 2016 value and multiplied by 100.
- CEX saving-rate proxy: `(aggregate income after taxes - aggregate expenditures) / aggregate income after taxes`.
- CEX non-mortgage debt proxy: `credit-card debt + student-loan debt + other-loan debt` per consumer unit.

## Interpretation Notes

- PCE slightly outpaced current-dollar GDP from 2016Q1 to 2025Q4, but only by a small margin.
- Exports and imports grew more slowly than PCE and GDP, so trade declined as a share of GDP in the expenditure-component view.
- Government consumption and investment grew below GDP, while private investment nearly matched PCE.
- CEX aggregate spending growth by income quintile was surprisingly even from 2016 to 2024, with the highest quintile showing the lowest indexed growth among the quintiles.
- The CEX saving-rate proxy shows a large persistent level divide by quintile, not a large 2016-2023 divergence.
- Non-mortgage debt declined from 2023 to 2024 for the upper three quintiles, but rose for the lowest two quintiles.

## Caveats

- Many comparisons are nominal. Use real series before making purchasing-power or productivity claims.
- The CEX saving-rate proxy is not the official BEA/BLS distributional personal saving rate.
- CEX debt excludes mortgages, vehicle principal, and home-equity debt.
- CEX debt-to-after-tax-income stops at 2023 because the local CEX income-after-tax quintile series was not available for 2024.
- Imports are charted as positive import spending in the GDP component index, even though imports subtract from GDP.

## Recommended Next Steps

- Add `cx.data.1.AllData` to the CEX Python fetcher so debt analysis is fully repeatable.
- Add tests that verify the CEX fetcher retrieves all raw files required for consumption, saving proxy, and debt analysis.
- Consider adding official BEA/BLS distributional personal saving data for a true saving-rate-by-quintile series.
- Consider adding Fed Distributional Financial Accounts or SCF debt measures to validate CEX debt patterns against balance-sheet data.
