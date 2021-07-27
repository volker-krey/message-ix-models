import logging
from copy import copy

import pytest
from pytest import mark, param

from message_ix_models import testing
from message_ix_models.model.structure import get_codes
from message_ix_models.testing import NIE

from message_data.model.transport import build, report, read_config

log = logging.getLogger(__name__)


@pytest.mark.parametrize("years", ["A", "B"])
@pytest.mark.parametrize(
    "regions_arg, regions_exp",
    [
        (None, "R11"),
        ("R11", "R11"),
        param("R12", "R12", marks=pytest.mark.xfail(raises=FileNotFoundError)),
        ("R14", "R14"),
        param("ISR", "ISR", marks=testing.NIE),
    ],
)
def test_get_spec(test_context, regions_arg, regions_exp, years):
    ctx = test_context
    if regions_arg:
        # Non-default value
        ctx.regions = regions_arg

    ctx.years = years

    read_config(ctx)

    # The spec can be generated
    spec = build.get_spec(ctx)

    # The required elements of the "node" set match the configuration
    nodes = get_codes(f"node/{regions_exp}")
    exp = list(map(str, nodes[nodes.index("World")].child))
    assert exp == spec["require"].set["node"]


@pytest.mark.parametrize(
    "regions, years, ldv, nonldv, solve",
    [
        ("R11", "A", None, None, False),  # 31 s
        ("R11", "B", None, None, False),
        param("R11", "A", None, None, True, marks=mark.slow),  # 44 s
        param("R11", "A", "US-TIMES MA3T", "IKARUS", False, marks=mark.slow),  # 43 s
        param("R11", "A", "US-TIMES MA3T", "IKARUS", True, marks=mark.slow),  # 74 s
        param("R14", "A", "US-TIMES MA3T", "IKARUS", False, marks=mark.slow),
        # Non-R11 configurations currently fail
        param("ISR", "A", None, None, False, marks=NIE),
        # Periods "B" currently fail
        param("R11", "B", "US-TIMES MA3T", "IKARUS", False, marks=(mark.slow, NIE)),
    ],
)
def test_build_bare_res(
    request, tmp_path, test_context, regions, years, ldv, nonldv, solve
):
    """Test that model.transport.build works on the bare RES, and the model solves."""
    # Pre-load transport config/metadata
    ctx = test_context
    ctx.regions = regions
    ctx.years = years

    read_config(ctx)

    # Manually modify some of the configuration per test parameters
    ctx["transport config"]["data source"]["LDV"] = ldv
    ctx["transport config"]["data source"]["non-LDV"] = nonldv

    # Generate the relevant bare RES
    scenario = testing.bare_res(request, ctx)

    # Build succeeds without error
    build.main(ctx, scenario, fast=True)

    # dump_path = tmp_path / "scenario.xlsx"
    # log.info(f"Dump contents to {dump_path}")
    # scenario.to_excel(dump_path)

    if solve:
        scenario.solve(solve_options=dict(lpmethod=4))

        # Use Reporting calculations to check the result
        result = report.check(scenario)
        assert result.all(), f"\n{result}"


@pytest.mark.ece_db
@pytest.mark.parametrize(
    "url",
    (
        "ixmp://ene-ixmp/CD_Links_SSP2_v2/baseline",
        "ixmp://ixmp-dev/ENGAGE_SSP2_v4.1.7/EN_NPi2020_1000f",
        "ixmp://ixmp-dev/ENGAGE_SSP2_v4.1.7/baseline",
        "ixmp://ixmp-dev/ENGAGE_SSP2_v4.1.7_ar5_gwp100/EN_NPi2020_1000_emif_new",
        "ixmp://ixmp-dev/MESSAGEix-GLOBIOM_R12_CHN/baseline#17",
        "ixmp://ixmp-dev/MESSAGEix-GLOBIOM_R12_CHN/baseline_macro#3",
        # Local clones of the above
        # "ixmp://clone-2021-06-09/ENGAGE_SSP2_v4.1.7/baseline",
        # "ixmp://clone-2021-06-09/ENGAGE_SSP2_v4.1.7/EN_NPi2020_1000f",
    ),
)
def test_build_existing(tmp_path, test_context, url, solve=False):
    """Test that model.transport.build works on certain existing scenarios.

    These are the ones listed in the documenation, at :ref:`transport-base-scenarios`.
    """
    ctx = test_context

    # Update the Context with the base scenario's `url`
    ctx.handle_cli_args(url=url)

    # Destination for built scenarios: uncomment one of
    # the platform prepared by the text fixture…
    ctx.dest_platform = copy(ctx.platform)
    # # or, a specific, named platform.
    # ctx.dest_platform = dict(name="local")

    # New model name for the destination scenario
    ctx.dest_scenario = copy(ctx.scenario_info)
    ctx.dest_scenario["model"] = f"MESSAGEix-Transport {ctx.dest_scenario['model']}"

    # Clone the base scenario to the test platform
    scenario = ctx.clone_to_dest()

    # Build succeeds without error
    build.main(ctx, scenario, fast=True)

    # commented: slow
    # dump_path = tmp_path / "scenario.xlsx"
    # log.info(f"Dump contents to {dump_path}")
    # scenario.to_excel(dump_path)

    if solve:
        scenario.solve(solve_options=dict(lpmethod=4))

        # Use Reporting calculations to check the result
        result = report.check(scenario)
        assert result.all(), f"\n{result}"
