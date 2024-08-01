import pytest

from message_ix_models.model.transport.config import Config
from message_ix_models.project.navigate import T35_POLICY
from message_ix_models.project.ssp import SSP_2017, SSP_2024
from message_ix_models.project.transport_futures import SCENARIO as TF_SCENARIO

FUTURES = (
    ("", TF_SCENARIO.BASE),
    ("base", TF_SCENARIO.BASE),
    ("A---", TF_SCENARIO.A___),
    ("debug", TF_SCENARIO.DEBUG),
    pytest.param("foo", None, marks=pytest.mark.xfail(raises=ValueError)),
)

NAVIGATE = (
    ("", T35_POLICY.REF),
    ("act", T35_POLICY.ACT),
    ("ele", T35_POLICY.ELE),
    ("tec", T35_POLICY.TEC),
    ("act+ele+tec", T35_POLICY.ALL),
    pytest.param("foo+act+tec", None, marks=pytest.mark.xfail(raises=ValueError)),
)

SSP = (
    ("1", SSP_2017["1"]),
    ("2", SSP_2017["2"]),
    ("3", SSP_2017["3"]),
    ("4", SSP_2017["4"]),
    ("5", SSP_2017["5"]),
    (SSP_2024["2"], SSP_2024["2"]),
)


class TestConfig:
    @pytest.fixture
    def c(self):
        yield Config()

    @pytest.mark.parametrize("input, expected", SSP)
    def test_ssp0(self, input, expected):
        """Set SSP through the constructor."""
        c = Config(ssp=input)  # Call succeeds
        assert expected == c.ssp  # The expected enum value is stored

    @pytest.mark.parametrize("input, expected", SSP)
    def test_ssp1(self, c, input, expected):
        """Set SSP on an existing instance."""
        c.ssp = input
        assert expected == c.ssp

    @pytest.mark.parametrize("input, expected", FUTURES)
    def test_futures_scenario0(self, input, expected):
        """Set Transport Futures scenario through the constructor."""
        c = Config(futures_scenario=input)  # Call succeeds
        assert expected == c.project["futures"]  # The expected enum value is set

    @pytest.mark.parametrize("input, expected", FUTURES)
    def test_futures_scenario1(self, c, input, expected):
        """Set Transport Futures scenario on an existing instance."""
        c.set_futures_scenario(input)
        assert expected == c.project["futures"]

    @pytest.mark.parametrize("input, expected", NAVIGATE)
    def test_navigate_scenario0(self, input, expected):
        """Set NAVIGATE scenario through the constructor."""
        c = Config(navigate_scenario=input)
        assert expected == c.project["navigate"]

    @pytest.mark.parametrize("input, expected", NAVIGATE)
    def test_navigate_scenario1(self, c, input, expected):
        """Set NAVIGATE scenario on an existing instance."""
        c.set_navigate_scenario(input)
        assert expected == c.project["navigate"]

    def test_scenario_conflict(self):
        # Giving both raises an exception
        with pytest.raises(
            ValueError,
            match=r"SCENARIO.A___ and T35_POLICY.ACT\|TEC are not compatible",
        ):
            c = Config(futures_scenario="A---", navigate_scenario="act+tec")

        # Also a conflict
        c = Config(navigate_scenario="act+tec")
        with pytest.raises(
            ValueError,
            match=r"SCENARIO.A___ and T35_POLICY.ACT\|TEC are not compatible",
        ):
            c.set_futures_scenario("A---")
