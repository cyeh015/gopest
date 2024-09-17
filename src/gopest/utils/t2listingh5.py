"""
Copyright 2013, 2014 University of Auckland.

This file is part of TIM (Tim Isn't Mulgraph).

    TIM is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    TIM is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with TIM.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
Wrap AUTOUGH2's hdf5 output as t2listing
"""

import h5py
import numpy as np

from t2listing import *
# from t2listing import listingtable
from mulgrids import fix_blockname, unfix_blockname

from pprint import pprint as pp
import unittest

class h5table(listingtable):
    """ Class emulating the listingtable class in PyTOUGH.

    Class for table in listing file, with values addressable by index (0-based)
    or row name, and column name: e.g. table[i] returns the ith row (as a
    dictionary), table[rowname] returns the row with the specified name, and
    table[colname] returns the column with the specified name.

    !!! IMPORTANT !!!
    .index needs to be set whenever listing object changed time index
    """
    def __init__(self, cols, rows, h5_table,
                 num_keys = 1, allow_reverse_keys = False,
                 index = 0):
        """ The row_format parameter is a dictionary with three keys,
        'key','index' and 'values'.  These contain the positions, in each row of
        the table, of the start of the keys, index and data fields.  The
        row_line parameter is a list containing, for each row of the table, the
        number of lines before it in the listing file, from the start of the
        table.  This is needed for TOUGH2_MP listing files, in which the rows
        are not in index order and can also be duplicated.

        h5_table should be the table within the h5 file.
        """
        self.column_name = cols
        self.row_name = rows
        self.num_keys = num_keys
        self.allow_reverse_keys = allow_reverse_keys
        self._col = dict([(c,i) for i,c in enumerate(cols)])
        self._row = dict([(r,i) for i,r in enumerate(rows)])
        self._h5_table = h5_table
        self._index = index # time index

    def __repr__(self):
        # h5 table lst._h5['element'][time index, eleme index, field index]
        return repr(self.column_name) + '\n' + repr(self._h5_table[self._index, :, :])

    def __getitem__(self, key):
        if isinstance(key, int):
            return dict(zip(['key'] + self.column_name, [self.row_name[key]] +
                            list(self._h5_table[self._index, key, :])))
        else:
            if key in self.column_name:
                return self._h5_table[self._index, :, self._col[key]]
            elif key in self.row_name:
                rowindex = self._row[key]
                return dict(zip(['key'] + self.column_name,
                                [self.row_name[rowindex]] +
                                list(self._h5_table[self._index, rowindex, :])))
            elif len(key) > 1 and self.allow_reverse_keys:
                revkey = key[::-1] # try reversed key for multi-key tables
                if revkey in self.row_name:
                    rowindex = self._row[revkey]
                    return dict(zip(['key'] + self.column_name,
                                    [self.row_name[rowindex][::-1]] +
                                    list(-self._h5_table[self._index, rowindex, :])))
            else: return None

    def __add__(self, other):
        raise NotImplementedError
        """Adds two listing tables together."""
        if self.column_name == other.column_name and self.row_name == other.row_name:
            from copy import copy
            result = listingtable(copy(self.column_name), copy(self.row_name), num_keys = self.num_keys,
                                  allow_reverse_keys = self.allow_reverse_keys)
            result._data = self._data + other._data
            return result
        else: raise Exception("Incompatible tables: can't be added together.")

    def __sub__(self, other):
        raise NotImplementedError
        """Subtracts one listing table from another."""
        if self.column_name == other.column_name and self.row_name == other.row_name:
            from copy import copy
            result = listingtable(copy(self.column_name), copy(self.row_name), num_keys = self.num_keys,
                                  allow_reverse_keys = self.allow_reverse_keys)
            result._data = self._data - other._data
            return result
        else: raise Exception("Incompatible tables: can't be subtracted.")


class t2listingh5(object):
    def __init__(self, filename):
        """
        """
        self._table = {}
        self._h5 = h5py.File(filename, 'r')
        self.filename = filename
        self.setup()
        self.simulator = 'AUTOUGH2_H5'

    def close(self):
        self._h5.close()

    def setup(self):
        self.fulltimes = self._h5['fulltimes']['TIME']
        self.num_fulltimes = len(self.fulltimes)
        self._index = 0 # this is the internal one
        ### element table
        if 'element' in self._h5:
            cols = [x.decode('utf-8') for x in self._h5['element_fields']]
            blocks = [fix_blockname(x.decode('utf-8')) for x in self._h5['element_names']]
            table = h5table(cols, blocks, self._h5['element'], num_keys=1)
            self._table['element'] = table
        ### connection table
        if 'connection' in self._h5:
            cols = [x.decode('utf-8') for x in self._h5['connection_fields'][:]]
            b1 = [fix_blockname(x.decode('utf-8')) for x in self._h5['connection_names1'][:]]
            b2 = [fix_blockname(x.decode('utf-8')) for x in self._h5['connection_names2'][:]]
            table = h5table(cols, list(zip(b1,b2)), self._h5['connection'], num_keys=2,
                            allow_reverse_keys=True)
            self._table['connection'] = table
        ### generation table
        if 'generation' in self._h5:
            cols = [x.decode('utf-8') for x in self._h5['generation_fields'][:]]
            blocks = [fix_blockname(x.decode('utf-8')) for x in self._h5['generation_eleme'][:]]
            geners = [fix_blockname(x.decode('utf-8')) for x in self._h5['generation_names'][:]]
            table = h5table(cols, list(zip(blocks,geners)), self._h5['generation'], num_keys=1)
            self._table['generation'] = table
        # makes tables in self._table accessible as attributes
        for key,table in self._table.items():
            setattr(self, key, table)
        # have to be get first table ready
        self.index = 0

    def history(self, selection, short=False, start_datetime=None):
        """
        short is not used at the moment
        """
        if isinstance(selection, tuple):
            selection = [selection]
        results = []
        for tbl,b,cname in selection:
            table_name, bi, fieldi = self.selection_index(tbl, b, cname)
            if bi < 0:
                bi = len(self.block_name_index) + bi
            ### important to convert cell index
            ys = self._h5[table_name][:,bi,fieldi]
            results.append((self.fulltimes, ys))
        if len(results) == 1: results = results[0]
        return results

    def selection_index(self, tbl, b, field):
        dname = {
            'e': 'element',
            'c': 'connection',
            'g': 'generation',
        }
        def eleme_index(b):
            if isinstance(b, str):
                bi = self.block_name_index[b]
            elif isinstance(b, int):
                bi = b
            else:
                raise Exception('.history() block must be an int or str: %s (%s)' % (str(b),str(type(b))))
            return bi
        def conne_index(b):
            if isinstance(b, tuple):
                bi = self.connection_name_index[(str(b[0]), str(b[1]))]
            elif isinstance(b, int):
                bi = b
            else:
                raise Exception('.history() conne must be an int or (str,str): %s (%s)' % (str(b),str(type(b))))
            return bi
        def gener_index(b):
            if isinstance(b, tuple):
                bi = self.generation_name_index[(str(b[0]), str(b[1]))]
            elif isinstance(b, int):
                bi = b
            else:
                raise Exception('.history() gener must be an int or (str,str): %s (%s)' % (str(b),str(type(b))))
            return bi
        iname = {
            'e': eleme_index,
            'c': conne_index,
            'g': gener_index,
        }
        if not hasattr(self, 'field_index'):
            self.field_index = {}
            for n,nn in dname.items():
                for i,ff in enumerate(self._h5[nn + '_fields']):
                    self.field_index[(n,ff)] = i
        return dname[tbl], iname[tbl](b), self.field_index[(tbl,field)]

    @property
    def block_name_index(self):
        if not hasattr(self, '_block_name_index'):
            self._block_name_index = {}
            # self._block_name_index.update({str(e):i for i,e in enumerate(self._h5['element_names'])})
            self._block_name_index.update({fix_blockname(str(e)):i for i,e in enumerate(self._h5['element_names'])})
        return self._block_name_index

    @property
    def connection_name_index(self):
        if not hasattr(self, '_connection_name_index'):
            a = self._h5['connection_names1']
            b = self._h5['connection_names2']
            self._connection_name_index = {}
            self._connection_name_index.update({(fix_blockname(str(x[0])),fix_blockname(str(x[1]))):i for i,x in enumerate(zip(a,b))})
        return self._connection_name_index

    @property
    def generation_name_index(self):
        if not hasattr(self, '_generation_name_index'):
            a = self._h5['generation_eleme']
            b = self._h5['generation_names']
            self._generation_name_index = {}
            # self._generation_name_index.update({(str(x[0]),str(x[1])):i for i,x in enumerate(zip(a,b))})
            # self._generation_name_index.update({(fix_blockname(str(x[0])),(str(x[1]))):i for i,x in enumerate(zip(a,b))})
            # self._generation_name_index.update({((str(x[0])),fix_blockname(str(x[1]))):i for i,x in enumerate(zip(a,b))})
            self._generation_name_index.update({(fix_blockname(str(x[0])),fix_blockname(str(x[1]))):i for i,x in enumerate(zip(a,b))})
        return self._generation_name_index


    def read_tables(self):
        """ copy values from h5 into listingtables, with slicing """
        if 'element' in self.table_names:
            self.element._index = self.index
            # for i,cname in enumerate(self.element.column_name):
            #     self.element._data[:,i] = self._h5['element'][self._index, :, i]
        if 'connection' in self.table_names:
            self.connection._index = self.index
            # for i,cname in enumerate(self.connection.column_name):
            #     self.connection._data[:,i] = self._h5['connection'][self._index, :, i]
        if 'generation' in self.table_names:
            self.generation._index = self.index
            # for i,cname in enumerate(self.generation.column_name):
            #     self.generation._data[:,i] = self._h5['generation'][self._index, :, i]

    def get_index(self): return self._index
    def set_index(self, i):
        self._index = i
        if self._index < 0: self._index += self.num_fulltimes
        self.read_tables()
    index = property(get_index, set_index)

    def first(self): self.index = 0
    def last(self): self.index = -1
    def next(self):
        """Find and read next set of results; returns false if at end of listing"""
        more = self.index < self.num_fulltimes - 1
        if more: self.index += 1
        return more
    def prev(self):
        """Find and read previous set of results; returns false if at start of listing"""
        more = self.index > 0
        if more: self.index -= 1
        return more

    def get_table_names(self):
        return sorted(self._table.keys())
    table_names = property(get_table_names)

    def get_time(self): return self.fulltimes[self.index]
    def set_time(self, t):
        if t < self.fulltimes[0]: self.index = 0
        elif t > self.fulltimes[-1]: self.index = -1
        else:
            dt = np.abs(self.fulltimes - t)
            self.index = np.argmin(dt)
    time = property(get_time, set_time)


class test_fivespot(unittest.TestCase):
    def setUp(self):
        self.lst_h = t2listingh5('fivespot.h5')
        self.lst_t= t2listing('expected.listing')

    def test_match_tables(self):
        # check row and column names
        def check_names(tbl):
            tbl_h = getattr(self.lst_h, tbl)
            tbl_t = getattr(self.lst_t, tbl)
            self.assertEqual(tbl_h.row_name, tbl_t.row_name)
            for i,field in enumerate(tbl_h.column_name):
                if tbl_t.column_name[i] in field:
                    match = True
                else:
                    match = False
                self.assertEqual(match, True, '%s: column name mismatch' % tbl)
        for tbl in ['element', 'connection', 'generation']:
            check_names(tbl)
        # check table values, after change index also
        def check_tables():
            rtol = 1.0e-5 # roughly 4~5 significant digits from text listing file
            for field in ['Temperature', 'Pressure', 'Vapour saturation']:
                np.testing.assert_allclose(self.lst_h.element[field],
                                           self.lst_t.element[field], rtol=rtol)
            for field in ['Mass flow', 'Enthalpy', 'Heat flow']:
                np.testing.assert_allclose(self.lst_h.connection[field],
                                           self.lst_t.connection[field], rtol=rtol)
            for field in ['Generation rate', 'Enthalpy']:
                np.testing.assert_allclose(self.lst_h.generation[field],
                                           self.lst_t.generation[field], rtol=rtol)
        check_tables()
        self.lst_h.last(); self.lst_t.last()
        check_tables()
        self.lst_h.first(); self.lst_t.first()
        check_tables()

        # check table with element index
        def check_table_by_index(i):
            tbl_h = self.lst_h.element[i]
            tbl_t = self.lst_t.element[i]
            for k in tbl_h.keys():
                if k == 'key':
                    self.assertEqual(tbl_h[k], tbl_t[k])
                else:
                    np.testing.assert_approx_equal(tbl_h[k], tbl_t[k], significant=5)
        for i in range(len(self.lst_h.element.row_name)):
            check_table_by_index(i)

        # check table with element name
        def check_table_by_name(b):
            tbl_h = self.lst_h.element[b]
            tbl_t = self.lst_t.element[b]
            for k in tbl_h.keys():
                if k == 'key':
                    self.assertEqual(tbl_h[k], tbl_t[k])
                else:
                    np.testing.assert_approx_equal(tbl_h[k], tbl_t[k], significant=5)
        for b in self.lst_h.element.row_name:
            check_table_by_index(b)

    def test_match_history(self):
        self.assertEqual(self.lst_h.num_fulltimes, self.lst_t.num_fulltimes)
        np.testing.assert_allclose(self.lst_h.fulltimes, self.lst_t.fulltimes)
        rtol = 1.0e-5
        # seems allfield names are identical with fivespot's EOS
        for sel in [('e', 'AA106', 'Pressure'),
                    ('e', 'AA 66', 'Temperature'),
                    ('c', ('AA 66', 'AA 67'), 'Mass flow'),
                    ('g', ('AA 11', 'PRO 1'), 'Generation rate'),
                    ('g', ('AA 11', 'PRO 1'), 'Enthalpy'),
                    ]:
            xs_h, ys_h = self.lst_h.history(sel)
            xs_t, ys_t = self.lst_t.history(sel)
            np.testing.assert_allclose(xs_h, xs_t, rtol=rtol)
            np.testing.assert_allclose(ys_h, ys_t, rtol=rtol)


if __name__ == '__main__':
    unittest.main(verbosity=2)
