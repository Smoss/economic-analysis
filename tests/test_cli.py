import pytest

from economic_analysis.cli import main


def test_fetch_all_dry_run_has_no_network_or_credentials(capsys, tmp_path):
    exit_code = main(["fetch", "all", "--dry-run", "--data-dir", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "bls_labor" in output
    assert "bea_pce" in output
    assert "scf_home_assets" in output
    assert "bea_gdp_industry" in output
    assert "would write" in output


def test_fetch_all_requires_bea_key_before_live_writes(monkeypatch, tmp_path):
    monkeypatch.delenv("BEA_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="BEA_API_KEY is required"):
        main(["fetch", "all", "--data-dir", str(tmp_path)])
