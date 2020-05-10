from functools import lru_cache
from itertools import product

import xarray as xr

from message_data.tools import Code, get_context, load_data, set_info


# Configuration files
METADATA = [
    # Information about MESSAGE-Transport
    ('transport', 'callback'),
    ('transport', 'config'),
    ('transport', 'set'),
    ('transport', 'technology'),
    # Information about the MESSAGE V model
    ('transport', 'migrate', 'set'),
]

# Files containing data for input calculations and assumptions
FILES = [
    'ldv_class',
    'mer_to_ppp',
    'population-suburb-share',
    'ma3t/population',
    'ma3t/attitude',
    'ma3t/driver',
]


def read_config():
    """Read the transport model configuration / metadata from file.

    Numerical values are converted to computation-ready data structures.

    Returns
    -------
    .Context
        The current Context, with the loaded configuration.
    """
    context = get_context()

    try:
        context['transport migrate set']
    except KeyError:
        # Not yet loaded
        pass
    else:
        # Already loaded
        return context

    for parts in METADATA:
        context.load_config(*parts)

    # Storage for exogenous data
    context.data = xr.Dataset()

    # Load data files
    for key in FILES:
        context.data[key] = load_data(context, 'transport', key,
                                      rtype=xr.DataArray)

    # Convert scalar parameters
    for key, val in context['transport callback'].pop('params').items():
        context.data[key] = eval(val) if isinstance(val, str) else val

    return context


@lru_cache()
def consumer_groups(rtype='code'):
    """Iterate over consumer groups in ``sets.yaml``."""
    dims = ['area_type', 'attitude', 'driver_type']

    # Retrieve configuration
    context = read_config()
    codes = [context['transport set'][d]['add'].keys() for d in dims]
    names = [context['transport set'][d]['add'] for d in dims]

    # Assemble group information
    result = dict(
        code=[],
        index=[],
        description=[],
        )

    for indices in product(*codes):
        # Tuple of the values along each dimension
        result['index'].append(indices)

        # String code
        result['code'].append(''.join(indices))

        # String description
        desc = ', '.join(n[i] for n, i in zip(names, indices)).lower()
        result['description'].append(desc)

    if rtype == 'description':
        return list(zip(result['code'], result['description']))
    elif rtype == 'indexers':
        # Three tuples of members along each dimension
        indexers = zip(*result['index'])
        indexers = {d: xr.DataArray(list(i), dims='consumer_group') for d, i
                    in zip(dims, indexers)}
        indexers['consumer_group'] = xr.DataArray(result['code'],
                                                  dims='consumer_group')
        return indexers
    elif rtype == 'code':
        return sorted(result['code'])
    else:
        raise ValueError(rtype)


def transport_technologies(by_cg=True, filter=[], with_desc=False):
    """Iterate over transport technologies in ``messagev-tech.yaml``.

    Technologies listed with `by_consumer_group` = :obj:`True` are returned
    once for each consumer group generated by :meth:`consumer_groups`.
    """
    config = get_context()['transport technology']

    group_of = {}
    for group_name, group_info in config['technology group'].items():
        group_of.update({tech: group_name for tech in group_info['tech']})

    for tech, info in config['technology'].items():
        if len(filter) and tech not in filter:
            continue

        # Identify the group to which the technology belongs
        group = config['technology group'].get(group_of.get(tech, None), {})

        if by_cg and group.get('by_consumer_group', False):
            # Technology has consumer groups
            if with_desc:
                for name, desc in consumer_groups(rtype='description'):
                    yield Code(
                        id=f'{tech}_{name}',
                        name=f"{info['description']} ({desc})",
                    )
            else:
                yield from [f'{tech}_{cg}' for cg in consumer_groups()]
        else:
            yield Code(tech, info.get('description', '')) if with_desc else tech


def add_commodity_and_level(df, default_level=None):
    # Add input commodity and level
    t_info = get_context()['transport technology']['technology']
    c_info = set_info("commodity")

    @lru_cache()
    def t_cl(t):
        input = t_info[t]['input']
        # Commodity must be specified
        commodity = input['commodity']
        # Use the default level for the commodity in the RES (per
        # commodity.yaml)
        level = (
            input.get('level', None)
            or c_info[c_info.index(commodity)].anno.get('level', None)
            or default_level
        )

        return commodity, level

    def func(row):
        row[['commodity', 'level']] = t_cl(row['technology'])
        return row

    return df.apply(func, axis=1)
