from sdr_toolkit.cli import _build_sources, _contacts_by_company
from sdr_toolkit.config import ICPConfig
from sdr_toolkit.llm import MockLLMClient
from sdr_toolkit.orchestrator import Pipeline
from sdr_toolkit.signals.demo_data import demo_companies, demo_contacts


def _run():
    icp = ICPConfig.default()
    llm = MockLLMClient()
    companies = demo_companies()
    contacts = _contacts_by_company(demo_contacts())
    sources = _build_sources(icp, live=False)
    pipeline = Pipeline(icp=icp, llm_client=llm, signal_sources=sources)
    return pipeline.run(companies, contacts), companies


def test_pipeline_scores_every_company_and_sorts_descending():
    result, companies = _run()
    assert len(result.packages) == len(companies)
    scores = [p.scored_account.combined_score for p in result.packages]
    assert scores == sorted(scores, reverse=True)


def test_pipeline_skips_expensive_agents_below_nurture_bar():
    result, _ = _run()
    low_scoring = [p for p in result.packages if p.scored_account.combined_score < 0.35]
    assert low_scoring, "expected at least one demo company below the nurture bar"
    assert all(p.dossier is None and p.qualification is None for p in low_scoring)


def test_pipeline_drafts_sequences_only_for_qualified_accounts_with_contacts():
    result, _ = _run()
    qualified = [p for p in result.packages if p.qualification and p.qualification.verdict == "qualified"]
    assert qualified, "expected at least one demo company to qualify"
    for pkg in qualified:
        assert len(pkg.sequences) == len(pkg.contacts)
        for contact in pkg.contacts:
            assert contact.id in pkg.sequences

    nurture_or_below = [p for p in result.packages if not p.qualification or p.qualification.verdict != "qualified"]
    assert all(p.sequences == {} for p in nurture_or_below)


def test_pipeline_respects_limit():
    icp = ICPConfig.default()
    llm = MockLLMClient()
    companies = demo_companies()
    contacts = _contacts_by_company(demo_contacts())
    sources = _build_sources(icp, live=False)
    pipeline = Pipeline(icp=icp, llm_client=llm, signal_sources=sources)
    result = pipeline.run(companies, contacts, limit=2)
    assert len(result.packages) == 2
