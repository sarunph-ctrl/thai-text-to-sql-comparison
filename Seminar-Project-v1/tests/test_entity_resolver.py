import pytest

from app.nlp.entity_resolver import resolve_entity, ResolutionStatus
from tests.fixtures import fresh_conn


@pytest.fixture()
def conn():
    c = fresh_conn()
    yield c
    c.close()


def test_exact_match(conn):
    r = resolve_entity(conn, "customers", "name", "สมชาย")
    assert r.status == ResolutionStatus.RESOLVED
    assert r.name == "สมชาย"


def test_exact_match_case_insensitive(conn):
    r = resolve_entity(conn, "customers", "name", "john smith")
    assert r.status == ResolutionStatus.RESOLVED
    assert r.id == 3


def test_substring_match(conn):
    r = resolve_entity(conn, "products", "name", "โน้ต")
    assert r.status == ResolutionStatus.RESOLVED
    assert r.name == "สมุดโน้ต"


def test_ambiguous_prefix(conn):
    r = resolve_entity(conn, "customers", "name", "สม")
    assert r.status == ResolutionStatus.AMBIGUOUS
    names = {c[1] for c in r.candidates}
    assert names == {"สมชาย", "สมหญิง"}


def test_not_found(conn):
    r = resolve_entity(conn, "customers", "name", "ไม่มีตัวตนแบบนี้แน่นอน")
    assert r.status == ResolutionStatus.NOT_FOUND


def test_empty_query_not_found(conn):
    r = resolve_entity(conn, "customers", "name", "")
    assert r.status == ResolutionStatus.NOT_FOUND


def test_rejects_unknown_table(conn):
    with pytest.raises(ValueError):
        resolve_entity(conn, "pg_shadow", "name", "postgres")
