"""Entity-resolution tests: exact blocking, fuzzy-name, contradiction guard."""

from src.models.normalized import NormalizedRecord, NormalizedValue
from src.models.value import ValueSource
from src.resolution.cluster import cluster_records


def nv(value, source="CSV", malformed=False):
    return NormalizedValue(value, ValueSource(source, "x", str(value), malformed))


def rec(source="CSV", *, name=None, email=None, phone=None):
    fields = {}
    if name:
        fields["full_name"] = [nv(name, source)]
    if email:
        fields["emails"] = [nv(email, source)]
    if phone:
        fields["phones"] = [nv(phone, source)]
    return NormalizedRecord(source=source, fields=fields)


def ids(clusters):
    return [sorted(r.first_value("full_name") or "?" for r in c) for c in clusters]


def test_exact_email_links_records():
    clusters = cluster_records([
        rec("CSV", name="Jane Doe", email="jane@x.com"),
        rec("Resume", name="Jane D", email="jane@x.com"),
    ])
    assert len(clusters) == 1


def test_exact_phone_links_records():
    clusters = cluster_records([
        rec("CSV", name="A", phone="+10000000000"),
        rec("Resume", name="B", phone="+10000000000"),
    ])
    assert len(clusters) == 1


def test_fuzzy_name_merges_when_one_side_lacks_strong_id():
    # Recruiter note has only a name; resume has the same name + an email.
    clusters = cluster_records([
        rec("Resume", name="Jonathan Smith", email="jon@x.com"),
        rec("Note", name="Jonathan Smith"),  # no email/phone
    ])
    assert len(clusters) == 1


def test_contradiction_guard_keeps_different_people_apart():
    # Same name, but DIFFERENT emails -> must stay two candidates.
    clusters = cluster_records([
        rec("CSV", name="John Smith", email="john1@x.com"),
        rec("ATS", name="John Smith", email="john2@y.com"),
    ])
    assert len(clusters) == 2


def test_different_surnames_not_compared():
    clusters = cluster_records([
        rec("CSV", name="Jane Doe"),
        rec("Resume", name="Jane Roe"),
    ])
    assert len(clusters) == 2


def test_below_threshold_not_merged():
    clusters = cluster_records([
        rec("CSV", name="Alan Turing"),
        rec("Note", name="Brian Turing"),
    ], fuzzy_threshold=95)
    assert len(clusters) == 2


def test_transitive_clustering_via_mixed_keys():
    # A~B by email, B~C by phone => A,B,C one cluster (union-find transitivity).
    clusters = cluster_records([
        rec("CSV", name="A", email="shared@x.com"),
        rec("Resume", name="B", email="shared@x.com", phone="+12223334444"),
        rec("ATS", name="C", phone="+12223334444"),
    ])
    assert len(clusters) == 1


def test_resolution_is_deterministic():
    records = [
        rec("Resume", name="Jonathan Smith", email="jon@x.com"),
        rec("Note", name="Jonathan Smith"),
        rec("CSV", name="Jane Doe", email="jane@x.com"),
    ]
    assert ids(cluster_records(records)) == ids(cluster_records(records))
