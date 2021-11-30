import logging

import message_ix
import pytest
from message_ix.reporting import Key
from message_ix_models import testing
from message_ix_models.model import bare
from pytest import param

from message_data.model.transport import demand, configure
from message_data.tools import assert_units

log = logging.getLogger(__name__)


@pytest.mark.parametrize("regions", ["R11", "R14", param("ISR", marks=testing.NIE)])
@pytest.mark.parametrize("years", ["A", "B"])
def test_demand_dummy(test_context, regions, years):
    """Consumer-group-specific commodities are generated."""
    ctx = test_context
    ctx.regions = regions
    ctx.years = years

    configure(ctx)

    info = bare.get_spec(ctx)["add"]
    args = (info.set["node"], info.set["year"], ctx["transport config"])

    # Returns empty dict without config flag set
    ctx["transport config"]["data source"]["demand dummy"] = False
    assert dict() == demand.dummy(*args)

    ctx["transport config"]["data source"]["demand dummy"] = True
    data = demand.dummy(*args)

    assert any(data["demand"]["commodity"] == "transport pax URLMM")


@pytest.mark.parametrize(
    "regions,years,N_node,mode_shares",
    [
        ("R11", "A", 11, None),
        ("R11", "B", 11, None),
        ("R11", "B", 11, "debug"),
        ("R11", "B", 11, "A---"),
        ("R14", "B", 14, None),
        param("ISR", "A", 1, None, marks=testing.NIE),
    ],
)
def test_exo(test_context, tmp_path, regions, years, N_node, mode_shares):
    """Exogenous demand calculation succeeds."""
    ctx = test_context
    ctx.regions = regions
    ctx.years = years
    ctx.output_path = tmp_path

    options = {"mode-share": mode_shares} if mode_shares is not None else dict()
    configure(ctx, None, options)

    spec = bare.get_spec(ctx)

    rep = message_ix.Reporter()
    demand.prepare_reporter(rep, context=ctx, exogenous_data=True, info=spec["add"])
    rep.configure(output_dir=tmp_path)

    for key, unit in (
        ("population:n-y", "Mpassenger"),
        ("GDP:n-y:PPP+capita", "kUSD / passenger / year"),
        ("votm:n-y", ""),
        ("PRICE_COMMODITY:n-c-y:transport+smooth", "USD / km"),
        ("cost:n-y-c-t", "USD / km"),
        ("transport pdt:n-y-t", "passenger km / year"),
        # These units are implied by the test of "transport pdt:*":
        # "transport pdt:n-y:total" [=] Mm / year
    ):
        try:
            # Quantity can be computed
            qty = rep.get(key)

            # Quantity has the expected units
            assert_units(qty, unit)

            # Quantity has the expected size on the n/node dimension
            assert N_node == len(qty.coords["n"])
        except AssertionError:
            # Something else
            print(f"\n\n-- {key} --\n\n")
            print(rep.describe(key))
            print(qty, qty.attrs)
            raise

    # Demand is expressed for the expected quantities
    data = rep.get("demand:ixmp")

    # Returns a dict with a single key/DataFrame
    df = data.pop("demand")
    assert 0 == len(data)

    assert {"transport pax RUEMF", "transport pax air"} < set(df["commodity"])

    # Demand covers the model horizon
    assert spec["add"].Y[-1] == max(
        df["year"].unique()
    ), "`demand` does not cover the model horizon"

    # Total demand by mode
    key = Key("transport pdt", "nyt")

    # Graph structure can be visualized
    import dask
    from dask.optimization import cull

    dsk, deps = cull(rep.graph, key)
    path = tmp_path / "demand-graph.pdf"
    log.info(f"Visualize compute graph at {path}")
    dask.visualize(dsk, filename=str(path))

    # Plots can be generated
    rep.add("demand plots", ["plot demand-exo", "plot demand-exo-capita"])
    rep.get("demand plots")


@pytest.mark.skip(reason="Requires user's context")
def test_from_scenario(user_context):
    url = "ixmp://reporting/CD_Links_SSP2_v2.1_clean/baseline"
    scenario, mp = message_ix.Scenario.from_url(url)

    demand.from_scenario(scenario)


@pytest.mark.parametrize(
    "nodes, data_source",
    [
        ("R11", "GEA mix"),
        ("R14", "SSP2"),
        ("R11", "SHAPE innovation"),
    ],
)
def test_cli(tmp_path, mix_models_cli, nodes, data_source):
    assert 0 == len(list(tmp_path.glob("*.csv")))

    result = mix_models_cli.invoke(
        [
            "transport",
            "gen-demand",
            f"--nodes={nodes}",
            "--years=B",
            data_source,
            str(tmp_path),
        ]
    )
    assert result.exit_code == 0, (result.exception, result.output)

    # 1 file created in the temporary path
    assert 1 == len(list(tmp_path.glob("*.csv")))
