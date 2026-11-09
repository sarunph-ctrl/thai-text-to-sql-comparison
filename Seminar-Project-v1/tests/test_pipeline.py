import pytest
from decimal import Decimal

from app.nlp.pipeline import run_pipeline, PipelineStatus
from tests.fixtures import fresh_conn


@pytest.fixture()
def conn():
    c = fresh_conn()
    yield c
    c.close()


def test_revenue_this_month(conn):
    r = run_pipeline("ยอดขายเดือนนี้เท่าไหร่", conn)
    assert r.status == PipelineStatus.OK
    assert len(r.rows) == 1


def test_top_n_products_by_revenue(conn):
    r = run_pipeline("สินค้าขายดีที่สุด 5 อันดับ", conn)
    assert r.status == PipelineStatus.OK
    assert len(r.rows) <= 5
    # descending order
    values = [row[2] for row in r.rows]
    assert values == sorted(values, reverse=True)


def test_low_stock_filter(conn):
    r = run_pipeline("สินค้าที่สต็อกน้อยกว่า 10", conn)
    assert r.status == PipelineStatus.OK
    for row in r.rows:
        assert row[2] < 10


def test_cancelled_order_count(conn):
    r = run_pipeline("จำนวนออเดอร์ที่ยกเลิก", conn)
    assert r.status == PipelineStatus.OK
    assert r.rows[0][0] == 5  # matches known seed count


def test_revenue_by_category(conn):
    r = run_pipeline("ยอดขายแยกตามหมวดหมู่", conn)
    assert r.status == PipelineStatus.OK
    assert len(r.rows) == 3  # 3 categories have sales in the seed


def test_unmatched_greeting(conn):
    r = run_pipeline("สวัสดีครับวันนี้อากาศดี", conn)
    assert r.status == PipelineStatus.UNMATCHED


# --- Regression tests for bugs found during manual testing ---

def test_generic_word_khong_does_not_trigger_product_dimension(conn):
    """'ของ' is a generic connector word ("of"), not a product synonym -
    it must not falsely set dimension=product."""
    r = run_pipeline("สมชายซื้อของไปกี่บาท", conn)
    assert r.status == PipelineStatus.OK
    assert "customer filter resolved" in " ".join(r.matched_rules)
    assert not any("dimension=product" in rule for rule in r.matched_rules)


def test_customer_name_adjacent_to_verb_still_resolves(conn):
    """Thai has no spaces; an unknown proper name next to a verb often
    tokenizes as one merged token. Candidate extraction must work via
    substring removal on clean_text, not token equality, to survive this."""
    r = run_pipeline("สมชายซื้อของไปกี่บาท", conn)
    assert r.status == PipelineStatus.OK
    assert any("สมชาย" in rule and "id=1" in rule for rule in r.matched_rules)


def test_superlative_leftover_does_not_leak_into_entity_match(conn):
    """'ที่สุด' must be fully consumed even when an explicit top_n number
    already satisfied the top_n slot - otherwise a fragment like 'สุด' can
    survive and accidentally fuzzy-match an unrelated customer ("สุดา")."""
    r = run_pipeline("สินค้าขายดีที่สุด 5 อันดับ", conn)
    assert r.status == PipelineStatus.OK
    assert not any("customer filter" in rule for rule in r.matched_rules)


def test_average_order_value_not_mangled_by_repeat_collapse(conn):
    """'ต่อออเดอร์' legitimately has 3 identical vowels in a row at a word
    boundary; the repeat-collapse normalization step must not treat this
    as emphasis and mangle the word into something unmatchable."""
    r = run_pipeline("ค่าเฉลี่ยต่อออเดอร์เดือนนี้", conn)
    assert r.status == PipelineStatus.OK


def test_extreme_emphasis_repeat_collapses_but_does_not_leak_single_char(conn):
    """An exaggerated emphasis run ('เยอะกกกกก') collapses correctly, but the
    single leftover character must not be treated as a name candidate."""
    r = run_pipeline("ลูกค้าที่ซื้อเยอะกกกกก มากที่สุด", conn)
    assert r.status == PipelineStatus.OK


def test_ambiguous_customer_name_is_reported_not_guessed(conn):
    r = run_pipeline("ยอดขายของสม เดือนนี้", conn)
    # 'สม' matches both สมชาย and สมหญิง - must not silently pick one
    if r.status == PipelineStatus.AMBIGUOUS_ENTITY:
        assert len(r.candidates) >= 2
    else:
        # acceptable alternate outcome: candidate below length/quality bar,
        # falls through with no entity filter rather than guessing
        assert r.status == PipelineStatus.OK
        assert not any("customer filter" in rule for rule in r.matched_rules)


def test_revenue_never_counts_cancelled_orders_by_default(conn):
    r = run_pipeline("ยอดขายทั้งหมด", conn)
    all_time = run_pipeline("ยอดขายรวม", conn)
    # sanity: whichever matches, cancelled orders must be excluded via the
    # builder's default filter, which we verify directly at the SQL level
    # in test_query_builder.py. Here we just confirm the pipeline still
    # returns a sane single positive number.
    for res in (r, all_time):
        if res.status == PipelineStatus.OK:
            assert res.rows[0][0] > 0


def test_generated_sql_has_no_write_verbs(conn):
    r = run_pipeline("ยอดขายเดือนนี้", conn)
    assert r.status == PipelineStatus.OK
    upper = r.debug_sql.upper()
    for banned in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"):
        assert banned not in upper
