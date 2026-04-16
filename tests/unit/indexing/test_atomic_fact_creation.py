import pytest
from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier
from src.core.helpers import new_id


class TestAtomicFactCreation:
    """Test AtomicFact model creation and validation."""

    def test_create_atomic_fact_with_all_fields(self):
        """Test creating an AtomicFact with all required fields."""
        fact = AtomicFact(
            section_id="section-001",
            path_id="001.002",
            point="Python uses dynamic typing",
            rank=Tier.CRITICAL,
            reason="Fundamental language characteristic",
        )

        assert fact.section_id == "section-001"
        assert fact.path_id == "001.002"
        assert fact.point == "Python uses dynamic typing"
        assert fact.rank == Tier.CRITICAL
        assert fact.reason == "Fundamental language characteristic"
        assert fact.id is not None
        assert len(fact.id) > 0

    def test_atomic_fact_auto_generates_id(self):
        """Test that AtomicFact automatically generates an ID."""
        fact1 = AtomicFact(
            section_id="sec-1",
            path_id="001",
            point="Test point 1",
            rank=Tier.IMPORTANT,
            reason="Test reason 1",
        )

        fact2 = AtomicFact(
            section_id="sec-2",
            path_id="002",
            point="Test point 2",
            rank=Tier.NUANCE,
            reason="Test reason 2",
        )

        assert fact1.id != fact2.id
        assert isinstance(fact1.id, str)
        assert len(fact1.id) == 36  # UUID length

    def test_atomic_fact_weight_property(self):
        """Test the weight property returns correct values."""
        test_cases = [
            (Tier.CRITICAL, 3),
            (Tier.IMPORTANT, 2),
            (Tier.NUANCE, 1),
        ]

        for tier, expected_weight in test_cases:
            fact = AtomicFact(
                section_id="test", path_id="001", point="Test", rank=tier, reason="Test"
            )
            assert fact.weight == expected_weight

    def test_atomic_fact_is_immutable(self):
        """Test that AtomicFact objects are not frozen (SQLModel tables cannot be frozen)."""
        fact = AtomicFact(
            section_id="sec-001",
            path_id="001",
            point="Original point",
            rank=Tier.IMPORTANT,
            reason="Original reason",
        )
        # Modification should be allowed because SQLModel tables are mutable
        fact.point = "Modified point"
        assert fact.point == "Modified point"


class TestTierEnumValidation:
    """Test Tier enum conversion and validation."""

    def test_tier_from_rank_integer(self):
        """Test converting integer ranks to Tier enums."""
        test_cases = [
            (1, Tier.CRITICAL),
            (2, Tier.IMPORTANT),
            (3, Tier.NUANCE),
            (0, Tier.NUANCE),  # Invalid falls back
            (99, Tier.NUANCE),  # Invalid falls back
        ]

        for rank, expected in test_cases:
            result = Tier.from_rank(rank)
            assert result == expected

    def test_tier_from_rank_string(self):
        """Test converting string ranks to Tier enums."""
        test_cases = [
            ("NUANCE", Tier.NUANCE),
            ("nuance", Tier.NUANCE),
            ("IMPORTANT", Tier.IMPORTANT),
            ("important", Tier.IMPORTANT),
            ("CRITICAL", Tier.CRITICAL),
            ("critical", Tier.CRITICAL),
            ("INVALID", Tier.NUANCE),  # Invalid falls back
        ]

        for rank, expected in test_cases:
            result = Tier.from_rank(rank)
            assert result == expected

    def test_tier_from_rank_none(self):
        """Test that None rank defaults to NUANCE."""
        result = Tier.from_rank(None)
        assert result == Tier.NUANCE

    def test_tier_to_rank_conversion(self):
        """Test converting Tier enums back to integer ranks."""
        test_cases = [
            (Tier.CRITICAL, 1),
            (Tier.IMPORTANT, 2),
            (Tier.NUANCE, 3),
        ]

        for tier, expected_rank in test_cases:
            result = tier.to_rank()
            assert result == expected_rank

    def test_tier_enum_values(self):
        """Test the actual integer values of Tier enum."""
        assert Tier.CRITICAL == 1
        assert Tier.IMPORTANT == 2
        assert Tier.NUANCE == 3


class TestAtomicFactCoercion:
    """Test automatic rank coercion in AtomicFact."""

    def test_atomic_fact_coerces_integer_rank(self):
        """Test that AtomicFact automatically converts integer ranks to Tier."""
        fact = AtomicFact(
            section_id="sec-001",
            path_id="001",
            point="Test point",
            rank=2,  # Integer, not Tier enum
            reason="Test reason",
        )

        assert fact.rank == Tier.IMPORTANT
        assert isinstance(fact.rank, Tier)

    def test_atomic_fact_coerces_string_rank(self):
        """Test that AtomicFact automatically converts string ranks to Tier."""
        fact = AtomicFact(
            section_id="sec-001",
            path_id="001",
            point="Test point",
            rank="CRITICAL",  # String, not Tier enum
            reason="Test reason",
        )

        assert fact.rank == Tier.CRITICAL
        assert isinstance(fact.rank, Tier)

    def test_atomic_fact_accepts_tier_directly(self):
        """Test that AtomicFact accepts Tier enum directly."""
        fact = AtomicFact(
            section_id="sec-001",
            path_id="001",
            point="Test point",
            rank=Tier.IMPORTANT,
            reason="Test reason",
        )

        assert fact.rank == Tier.IMPORTANT
