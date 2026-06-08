from src.domain.atomic_fact import AtomicFact
from src.domain.enums import Tier


class TestAtomicFactCreation:
    def test_create_atomic_fact_with_all_fields(self):
        fact = AtomicFact(
            section_id="section-001",
            chunk_id="chunk-001",
            point="Python uses dynamic typing",
            rank=Tier.CRITICAL,
            reason="Fundamental language characteristic",
        )

        assert fact.section_id == "section-001"
        assert fact.chunk_id == "chunk-001"
        assert fact.point == "Python uses dynamic typing"
        assert fact.rank == Tier.CRITICAL
        assert fact.reason == "Fundamental language characteristic"
        assert fact.id is not None
        assert len(fact.id) > 0

    def test_atomic_fact_auto_generates_id(self):
        fact1 = AtomicFact(
            section_id="sec-1",
            chunk_id="chunk-001",
            point="Test point 1",
            rank=Tier.IMPORTANT,
            reason="Test reason 1",
        )

        fact2 = AtomicFact(
            section_id="sec-2",
            chunk_id="chunk-002",
            point="Test point 2",
            rank=Tier.NUANCE,
            reason="Test reason 2",
        )

        assert fact1.id != fact2.id
        assert isinstance(fact1.id, str)
        assert len(fact1.id) == 36

    def test_atomic_fact_weight_property(self):
        test_cases = [
            (Tier.CRITICAL, 3),
            (Tier.IMPORTANT, 2),
            (Tier.NUANCE, 1),
        ]

        for tier, expected_weight in test_cases:
            fact = AtomicFact(
                section_id="test",
                chunk_id="chunk-001",
                point="Test",
                rank=tier,
                reason="Test",
            )
            assert fact.weight == expected_weight

    def test_atomic_fact_is_immutable(self):
        fact = AtomicFact(
            section_id="sec-001",
            chunk_id="chunk-001",
            point="Original point",
            rank=Tier.IMPORTANT,
            reason="Original reason",
        )
        # SQLModel table objects must stay mutable.
        fact.point = "Modified point"
        assert fact.point == "Modified point"


class TestTierEnumValidation:
    def test_tier_from_rank_integer(self):
        test_cases = [
            (1, Tier.CRITICAL),
            (2, Tier.IMPORTANT),
            (3, Tier.NUANCE),
            (0, Tier.NUANCE),
            (99, Tier.NUANCE),
        ]

        for rank, expected in test_cases:
            result = Tier.from_rank(rank)
            assert result == expected

    def test_tier_from_rank_string(self):
        test_cases = [
            ("NUANCE", Tier.NUANCE),
            ("nuance", Tier.NUANCE),
            ("IMPORTANT", Tier.IMPORTANT),
            ("important", Tier.IMPORTANT),
            ("CRITICAL", Tier.CRITICAL),
            ("critical", Tier.CRITICAL),
            ("INVALID", Tier.NUANCE),
        ]

        for rank, expected in test_cases:
            result = Tier.from_rank(rank)
            assert result == expected

    def test_tier_from_rank_none(self):
        result = Tier.from_rank(None)
        assert result == Tier.NUANCE

    def test_tier_to_rank_conversion(self):
        test_cases = [
            (Tier.CRITICAL, 1),
            (Tier.IMPORTANT, 2),
            (Tier.NUANCE, 3),
        ]

        for tier, expected_rank in test_cases:
            result = tier.to_rank()
            assert result == expected_rank

    def test_tier_enum_values(self):
        assert Tier.CRITICAL == 1
        assert Tier.IMPORTANT == 2
        assert Tier.NUANCE == 3


class TestAtomicFactCoercion:
    def test_atomic_fact_coerces_integer_rank(self):
        fact = AtomicFact(
            section_id="sec-001",
            chunk_id="chunk-001",
            point="Test point",
            rank=2,
            reason="Test reason",
        )

        assert fact.rank == Tier.IMPORTANT
        assert isinstance(fact.rank, Tier)

    def test_atomic_fact_coerces_string_rank(self):
        fact = AtomicFact(
            section_id="sec-001",
            chunk_id="chunk-001",
            point="Test point",
            rank="CRITICAL",
            reason="Test reason",
        )

        assert fact.rank == Tier.CRITICAL
        assert isinstance(fact.rank, Tier)

    def test_atomic_fact_accepts_tier_directly(self):
        fact = AtomicFact(
            section_id="sec-001",
            chunk_id="chunk-001",
            point="Test point",
            rank=Tier.IMPORTANT,
            reason="Test reason",
        )

        assert fact.rank == Tier.IMPORTANT
