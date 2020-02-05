from contextlib import contextmanager
from itertools import product
import logging.config
from pathlib import Path

import yaml
import pandas as pd
import xarray as xr


METADATA = [
    # Information about message_ix
    ('parameter',),
    # Information about MESSAGE-Transport
    ('transport', 'callback'),
    ('transport', 'config'),
    ('transport', 'set'),
    ('transport', 'technology'),
    # Information about the MESSAGE V model
    ('transport', 'migrate', 'set'),
]


def read_config(context):
    """Read the transport model configuration from file."""

    for parts in METADATA:
        context.load_config(*parts)

    # Storage for exogenous data
    context.data = xr.Dataset()

    # Convert files to xr.DataArrays
    for key, dims in context['transport callback'].pop('files').items():
        context.data[key] = xr.DataArray.from_series(
            pd.read_csv(context.get_path('transport', key).with_suffix('.csv'),
                        index_col=0)
            .rename_axis(dims[1], axis=1)
            .stack())

    # Convert scalar parameters
    for key, val in context['transport callback'].pop('params').items():
        context.data[key] = eval(val) if isinstance(val, str) else val

    # Configure logging
    with open(Path(__file__).parent / 'logging.yaml') as f:
        logging.config.dictConfig(yaml.safe_load(f))


def consumer_groups(context, with_desc=False):
    """Iterate over consumer groups in ``sets.yaml``."""
    dims = ['location', 'attitude', 'frequency']
    cfg = context['transport set']['consumer groups']

    # Assemble technology names
    keys = [cfg[d].keys() for d in dims]
    name = [''.join(k) for k in product(*keys)]

    if with_desc:
        # Assemble technology descriptions
        vals = [cfg[d].values() for d in dims]
        desc = [', '.join(v).lower() for v in product(*vals)]

        yield from sorted(zip(name, desc))
    else:
        yield from sorted(name)


def transport_technologies(context, by_cg=True, filter=[], with_desc=False):
    """Iterate over transport technologies in ``messagev-tech.yaml``.

    Technologies listed with `by_consumer_group` = :obj:`True` are returned
    once for each consumer group generated by :meth:`consumer_groups`.
    """
    for tech, info in context['transport technology']['technology'].items():
        if len(filter) and tech not in filter:
            continue

        if by_cg and info.get('by_consumer_group', False):
            if with_desc:
                for name, desc in consumer_groups(with_desc=True):
                    yield f'{tech}_{name}', \
                        f"{info['description']} ({desc})"
            else:
                yield from [f'{tech}_{cg}' for cg in consumer_groups()]
        else:
            yield (tech, info.get('description', '')) if with_desc else tech


@contextmanager
def silence_log():
    """Context manager to temporarily silence log output."""
    # Get the main logger
    main_log = logging.getLogger('.'.join(__name__.split('.')[:-1]))

    try:
        main_log.setLevel(100)
        yield
    finally:
        main_log.setLevel(logging.INFO)
