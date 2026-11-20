from augurai.config import load_settings


def test_loads_repo_config():
    s = load_settings()
    assert s.timezone == "Africa/Tunis"
    assert len(s.seed_people) == 16
    assert {p.id for p in s.seed_people} >= {"matt-pocock", "lauren-tan"}
    assert s.tn_job_board is None
