import numpy as np
from pandas.core.index import _ensure_index
from pandas.core.internals import BlockManager
from pandas.core.generic import NDFrame
from pandas.core.frame import DataFrame
from pandas.core.index import RangeIndex, Index
from pandas.core.categorical import Categorical, CategoricalDtype


def empty(types, size, cats=None, cols=None, index_type=None, index_name=None):
    """
    Create empty DataFrame to assign into

    Parameters
    ----------
    types: like np record structure, 'i4,u2,f4,f2,f4,M8,m8', or using tuples
        applies to non-categorical columns. If there are only categorical
        columns, an empty string of None will do.
    size: int
        Number of rows to allocate
    cats: dict {col: labels}
        Location and labels for categorical columns, e.g., {1: ['mary', 'mo]}
        will create column index 1 (inserted amongst the numerical columns)
        with two possible values. If labels is an integers, `{'col': 5}`,
        will generate temporary labels using range. If None, or column name
        is missing, will assume 16-bit integers (a reasonable default).
    cols: list of labels
        assigned column names, including categorical ones.

    Returns
    -------
    - dataframe with correct shape and data-types
    - list of numpy views, in order, of the columns of the dataframe. Assign
        to this.
    """
    df = DataFrame()
    cols = cols or range(cols)
    if isinstance(types, str):
        types = types.split(',')
    for t, col in zip(types, cols):
        if str(t) == 'category':
            if cats is None or col not in cats:
                df[str(col)] = Categorical([], categories=range(2**10),
                                           fastpath=True)
            elif isinstance(cats[col], int):
                df[str(col)] = Categorical([], categories=range(cats[col]),
                                           fastpath=True)
            else:  # explicit labels list
                df[str(col)] = Categorical([], categories=cats[col],
                                           fastpath=True)
        else:
            df[str(col)] = np.empty(0, dtype=t)

    if index_type is not None:
        if index_name is None:
            raise ValueError('If using an index, must give an index name')
        index = np.empty(size, dtype=index_type)
        axes = [df.columns.values.tolist(), index]
    else:
        axes = [df.columns.values.tolist(), RangeIndex(size)]

    # allocate and create blocks
    blocks = []
    codes = []
    for block, col in zip(df._data.blocks, df.columns):
        if isinstance(block.dtype, CategoricalDtype):
            categories = block.values.categories
            code = np.zeros(shape=size, dtype=block.values.codes.dtype)
            values = Categorical(values=code, categories=categories,
                                 fastpath=True)
        else:
            new_shape = (block.values.shape[0], size)
            values = np.empty(shape=new_shape, dtype=block.values.dtype)

        new_block = block.make_block_same_class(
                values=values, placement=block.mgr_locs.as_array)
        blocks.append(new_block)
        if isinstance(block.dtype, CategoricalDtype):
            codes.append((code, new_block.values))

    # create block manager
    df = DataFrame(BlockManager(blocks, axes))

    # create views
    views = {}
    for col in df:
        dtype = df[col].dtype
        if str(dtype) == 'category':
            views[col], views[col+'-catdef'] = codes.pop(0)
        else:
            these_blocks = [b for b in blocks if b.dtype == dtype]
            ind = [col for col, dt in df.dtypes.iteritems()
                   if dt == dtype].index(col)
            if len(these_blocks) > 1:
                views[col] = these_blocks[ind].values
            else:
                views[col] = these_blocks[0].values[ind, :]
    if index_type is not None:
        views[index_name] = index
    df.index.name = index_name
    return df, views
