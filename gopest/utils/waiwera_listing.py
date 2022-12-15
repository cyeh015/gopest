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
Wrap Waiwera's hdf5 output as t2listing
"""

import h5py
import numpy as np

from mulgrids import mulgrid
from t2listing import listingtable

import json
import time
import unittest
from pprint import pprint as pp

class wlisting(object):
    def __init__(self, filename=None, geo=None, fjson=None, size_check=True):
        """ Waiwera h5 output pretending to be t2listing

        If corresponding geo is supplied, wlisting can behave more like
        t2listing, which includes atmosphere blocks

        If Waiwera input json is provided, then .generation has .row_name using
        (t2 block name, source name) instead of (cell index, source index).
        """
        self._table = {}
        if isinstance(geo, str):
            self.geo = mulgrid(geo)
        else:
            self.geo = geo
        if self.geo is not None:
            if self.geo.block_order != 'dmplex':
                raise Exception("wlisting loading Waiwera output file requires a geometry with .block_order = 'dmplex'")
        if isinstance(fjson, str):
            with open(fjson, 'r') as f:
                self.wjson = json.load(f)
        else:
            self.wjson = json
        self._h5 = h5py.File(filename, 'r')
        self.filename = filename
        self.simulator = 'waiwera'
        self.size_check = size_check # raise Exception if number of block does not match geo
        self.setup()

    def setup(self):
        self.cell_idx = self._h5['cell_index'][:,0]
        self.fulltimes = self._h5['time'][:,0]
        self.num_fulltimes = len(self.fulltimes)
        self._index = 0
        ### checks:
        nh5 = len(self.cell_idx)
        if self.geo is not None:
            print('wlisting.element: uses mulgrid block name (str) as key.')
            nb = self.geo.num_blocks - self.geo.num_atmosphere_blocks
            if self.size_check and nh5 != nb:
                msg = 'HDF5 result %s has %i cells different from geometry %s (%i excl. atmosphere blocks)' % (
                    self.filename, nh5, self.geo.filename, nb)
                raise Exception(msg)
            if nh5 < nb:
                msg = 'HDF5 result %s has %i cells less than from geometry %s (%i excl. atmosphere blocks)' % (
                    self.filename, nh5, self.geo.filename, nb)
                raise Exception(msg)
            # blocks is seen by TIM/geo, w_blocks is used by waiwera-h5/json
            blocks = self.geo.block_name_list
            w_blocks = self.geo.block_name_list[self.geo.num_atmosphere_blocks:]
            if nh5 > nb:
                # assumes they are MINC blocks
                blocks += ['     '+str(i) for i in range(nh5 - nb)]
                w_blocks += ['     '+str(i) for i in range(nh5 - nb)]
        else:
            print('wlisting.element: uses waiwera natural index (as str) as key.')
            blocks = [str(i) for i in range(nh5)]
            w_blocks = blocks
        ### element table
        if 'cell_fields' in self._h5:
            cols = sorted([c for c in self._h5['cell_fields'].keys() if c.startswith('fluid_')])
            table = listingtable(cols, blocks, num_keys=1)
            self._table['element'] = table
        ### connection table
        if 'face_fields' in self._h5:
            cid1 = self._h5['face_cell_1'][:,0]
            cid2 = self._h5['face_cell_2'][:,0]
            # .face_idx equivalent to .cell_idx and .source_idx, which maps waiwera h5 table into
            # geo/mulgrid order, there is no "natural order" of faces in waiwera, so we have to
            # build one here
            self.face_idx = []
            self.face_idx_dir = []
            if self.geo is not None:
                print('wlisting.connection: tuple of mulgrid block names (str, str) as key.')
                face_keys = self.geo.block_connection_name_list
                # w_boundary is a list of dict, in the order of wjson boundaries, each dict has key
                # of block1, gives name of b2.
                w_boundary = []
                if self.wjson is not None and 'boundaries' in self.wjson:
                    for bd in self.wjson['boundaries']:
                        b2_names = {}
                        for i1 in bd['faces']['cells']:
                            b1 = w_blocks[i1]
                            b2 = '     ' # default empty , overwritten if atmosphere
                            if bd['faces']['normal'] == [0.0, 0.0, 1.0]:
                                # if connect upwards, assume atmospheric, use mulgrid atm block names
                                b1_col = self.geo.column[self.geo.column_name(b1)]
                                b1_lay = self.geo.layer[self.geo.layer_name(b1)]
                                if self.geo.column_surface_layer(b1_col).name == b1_lay.name:
                                    if self.geo.atmosphere_type == 0:
                                        b2 = self.geo.block_name_list[0]
                                    elif self.geo.atmosphere_type == 1:
                                        b2 = self.geo.block_name(self.geo.layerlist[0].name, b1_col.name)
                            b2_names[b1] = b2
                        w_boundary.append(b2_names)
                # this translate waiwera cell ids in (face_cell_1, face_cell_2) into block names
                # w_connection_name_index has keys of (b1 name, b2 name), value is waiwera face index
                # ordered as in h5 file
                w_connection_name_index = {}
                self.w_connection_index_index = {} # useful if given two waiwera cell indices
                for i,(c1,c2) in enumerate(zip(cid1, cid2)):
                    self.w_connection_index_index[(c1,c2)] = i
                    b1 = w_blocks[c1]
                    if c2 < 0:
                        if w_boundary:
                            # face_cell_2 contains the negative of the (1-based) index of the boundaries
                            # specified in json
                            b2 = w_boundary[-c2-1][b1]
                        else:
                            # either wai JSON not loaded OR none are standard atm conne
                            b2 = '     '
                            # simply assumes atm conne if top of the model
                            b1_col = self.geo.column[self.geo.column_name(b1)]
                            b1_lay = self.geo.layer[self.geo.layer_name(b1)]
                            if self.geo.column_surface_layer(b1_col).name == b1_lay.name:
                                if self.geo.atmosphere_type == 0:
                                    b2 = self.geo.block_name_list[0]
                                elif self.geo.atmosphere_type == 1:
                                    b2 = self.geo.block_name(self.geo.layerlist[0].name, b1_col.name)
                    else:
                        b2 = w_blocks[c2]
                    w_connection_name_index[(b1,b2)] = i
                for c in self.geo.block_connection_name_list:
                    # (cell1, cell2) positive means cell1 -> cell2
                    # NOTE this is opposite to T2/AUT2's result convention!
                    if c in w_connection_name_index:
                        self.face_idx.append(w_connection_name_index[c])
                        self.face_idx_dir.append(-1.0)
                    elif c[::-1] in w_connection_name_index:
                        self.face_idx.append(w_connection_name_index[c[::-1]])
                        self.face_idx_dir.append(1.0)
                    else:
                        debugxx = []
                        for key in w_connection_name_index:
                            if c[0] in key:
                                debugxx.append(key)
                        msg = str(debugxx)
                        msg += '\nMulgrid connection name %s not found in Waiwera H5 output.' % str(c)
                        raise Exception(msg)
            else:
                print('wlisting.connection: tuple of natural cell indices (as str, as str) as key.')
                # keeps whatever order is in h5, NOTE the order is unpredictable
                face_keys = [(str(i), str(j)) for i,j in zip(cid1, cid2)]
                self.face_idx = list(range(len(cid1)))
                self.face_idx_dir = [-1.0] * len(cid1)

            self.face_idx_dir = np.array(self.face_idx_dir)
            cols = sorted([c for c in self._h5['face_fields'].keys() if c.startswith('flux_')])
            table = listingtable(cols, face_keys, num_keys=2, allow_reverse_keys=True)
            self._table['connection'] = table
        ### gener table
        if 'source_fields' in self._h5:
            self.source_name_index = {} # allows either source name or (block name, gener name) as key
            skip_cols = ['source_' + n for n in ['source_index', 'local_source_index', 'natural_cell_index', 'local_cell_index']]
            cols = sorted([c for c in self._h5['source_fields'].keys() if c.startswith('source_') and c not in skip_cols])
            self.source_idx = self._h5['source_index'][:,0]
            source_keys = None
            if self.geo is not None and self.wjson is not None:
                if 'source' in self.wjson and len(self.wjson['source']) == len(self.source_idx):
                    if all(['name' in s for s in self.wjson['source']]) and all(['cell' in s for s in self.wjson['source']]):
                        # each source has a name, each source has a single cell
                        print('wlisting.generation: detects matching Waiwera input JSON and HDF5 source_fields, use (block name, source name) as key.')
                        cid = [w_blocks[s['cell']] for s in self.wjson['source']]
                        gid = [str(s['name']) for s in self.wjson['source']]
                        source_keys = list(zip(cid, gid))
                        for i,gk in enumerate(source_keys):
                            self.source_name_index[gk] = i
                    for i,s in enumerate(self.wjson['source']):
                        if 'name' in s:
                            self.source_name_index[s['name']] = i
            if source_keys is None:
                print('wlisting.generation: use source index (as str) as key.')
                # use source index (as str) as key
                source_keys = [str(i) for i in range(len(self.source_idx))]
                table = listingtable(cols, source_keys, num_keys=1)
            else:
                # source_keys is (bname, gname) as in original t2listing
                table = listingtable(cols, list(zip(cid, gid)), num_keys=2)
            self._table['generation'] = table
        # makes tables in self._table accessible as attributes
        for key,table in self._table.items():
            setattr(self, key, table)
        # have to be get first table ready
        self.index = 0

    def history(self, selection, short=False, start_datetime=None):
        """ Returns time histories for specified selection of table type, names
        (or indices) and column names.  This is implemented to be similar to
        t2listing's .history().

        ('e', block name/index, column name)
            for cell_fields, cell can be specified as Waiwera natural cell index
            (int) or mulgrid's block name (str)

        ('c', (c1, c2), column name)
            for face_fields, a face/connection can be specified by a tuple of
            Waiwera's natural cell index (int, int) or mulgrid's block names
            (str, str).

        ('g', g, column name) OR ('g', (b,g), column name)
            for source_fields, a gener/source can be specified by an index
            (int), a source name (str), or a tuple of (block name, source name)
            ((str, str)).  The tuple option is only available if each source has
            a name and each source has a single cell in the Waiwera JSON input.

        short and start_datetime are not implemented at the moment
        """
        if short is True: raise Exception('.history() short=True not implemented yet')
        if start_datetime is not None: raise Exception('.history() start_datetime not implemented yet')
        if isinstance(selection, tuple):
            selection = [selection]
        results = []
        for tbl,b,cname in selection:
            if tbl == 'e':
                if isinstance(b, str):
                    bi = self.geo.block_name_index[b]
                elif isinstance(b, unicode):
                    bi = self.geo.block_name_index[str(b)]
                elif isinstance(b, int):
                    bi = b
                else:
                    raise Exception('.history() block must be an int or str: %s (%s)' % (str(b),str(type(b))))
                if bi < 0:
                    bi = self.geo.num_blocks + bi
                if bi < self.geo.num_atmosphere_blocks:
                    raise Exception('.history() does not support extracting results for atmosphere blocks')
                ### important to convert cell index
                bbi = self.cell_idx[bi-self.geo.num_atmosphere_blocks]
                ys = self._h5['cell_fields'][cname][:,bbi]
                results.append((self.fulltimes, ys))
            elif tbl == 'c':
                if isinstance(b[0], int):
                    # (i1, i2) assume both are integer cell index in Waiwera sense
                    cci = self.w_connection_index_index[b]
                elif isinstance(b[0], str):
                    # (b1, b2) assume both are string block names in mulgrid
                    if self.geo is None:
                        raise Exception('Mulgrid geometry is required if connection tuple is specified by block names.')
                    ci = self.geo.block_connection_name_index[b]
                    cci = self.face_idx[ci]
                ys = self._h5['face_fields'][cname][:,cci]
                results.append((self.fulltimes, ys))
            elif tbl == 'g':
                if isinstance(b, tuple):
                    # (block name, source name) both str
                    gi = self.source_name_index[b]
                elif isinstance(b, str):
                    # single natural source index !! diff from TOUGH2
                    gi = self.source_name_index[b]
                if isinstance(b, int):
                    # directly as source index
                    gi = b
                ggi = self.source_idx[gi]
                ys = self._h5['source_fields'][cname][:,ggi]
                results.append((self.fulltimes, ys))
            else:
                raise Exception('Unsupported .history() selection table type: %s' % tbl)
        if len(results) == 1: results = results[0]
        return results

    def read_tables(self):
        """ copy values from h5 into listingtables, with slicing """
        if 'element' in self.table_names:
            nh5 = len(self.cell_idx)
            for i,cname in enumerate(self.element.column_name):
                self.element._data[-nh5:,i] = self._h5['cell_fields'][cname][self._index][self.cell_idx]
        if 'connection' in self.table_names:
            for i,cname in enumerate(self.connection.column_name):
                # re-order as geo.block_connection_name_list and reverse values if required
                self.connection._data[:,i] = self._h5['face_fields'][cname][self._index][self.face_idx] * self.face_idx_dir
        if 'generation' in self.table_names:
            for i,cname in enumerate(self.generation.column_name):
                self.generation._data[:,i] = self._h5['source_fields'][cname][self._index][self.source_idx]

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


class test_medium(unittest.TestCase):
    def setUp(self):
        from mulgrids import mulgrid
        self.geo = mulgrid('g2medium.dat')
        self.lst = wlisting('2DM002.h5', self.geo)

    def test_atm_blocks(self):
        self.assertEqual(len(self.lst.element.row_name), self.geo.num_blocks)
        # atmosphere blocks should be zero
        self.assertEqual(
            list(self.lst.element['fluid_temperature'][:self.geo.num_atmosphere_blocks]),
            [0.0] * self.geo.num_atmosphere_blocks)
        # even after change index
        self.index = 1
        self.assertEqual(
            list(self.lst.element['fluid_temperature'][:self.geo.num_atmosphere_blocks]),
            [0.0] * self.geo.num_atmosphere_blocks)

    def test_tables(self):
        self.assertEqual(self.lst.table_names, ['element', 'generation'])
        cols = [
            'fluid_liquid_capillary_pressure',
            'fluid_liquid_density',
            'fluid_liquid_internal_energy',
            'fluid_liquid_relative_permeability',
            'fluid_liquid_saturation',
            'fluid_liquid_specific_enthalpy',
            'fluid_liquid_viscosity',
            'fluid_liquid_water_mass_fraction',
            'fluid_phases',
            'fluid_pressure',
            'fluid_region',
            'fluid_temperature',
            'fluid_vapour_capillary_pressure',
            'fluid_vapour_density',
            'fluid_vapour_internal_energy',
            'fluid_vapour_relative_permeability',
            'fluid_vapour_saturation',
            'fluid_vapour_specific_enthalpy',
            'fluid_vapour_viscosity',
            'fluid_vapour_water_mass_fraction',
            'fluid_water_partial_pressure']
        self.assertEqual(sorted(self.lst.element.column_name), sorted(cols))
        cols = [
            'source_component',
            'source_enthalpy',
            'source_rate',
            ]
        self.assertEqual(sorted(self.lst.generation.column_name), sorted(cols))

    def test_basic_properties(self):
        self.assertEqual(self.lst.num_fulltimes, 2)
        np.testing.assert_almost_equal(
            self.lst.fulltimes,
            [0.0, 1.0E16],
            decimal=7)

    def test_index(self):
        self.assertEqual(self.lst.index, 0)
        self.assertAlmostEqual(self.lst.time, 0.0)
        np.testing.assert_almost_equal(
            self.lst.element['fluid_temperature'][-5:],
            [15.0, 15.0, 15.0, 15.0, 15.0]
            )

        self.lst.index = 1
        self.lst.index = 1
        self.assertEqual(self.lst.index, 1)
        self.assertAlmostEqual(self.lst.time, 1.0E16)
        np.testing.assert_almost_equal(
            self.lst.element['fluid_temperature'][-5:],
            [235.7365710, 234.266913, 233.142164, 232.376319, 231.98525],
            decimal=4
            )

        self.lst.index = 0
        self.assertEqual(self.lst.index, 0)
        self.assertAlmostEqual(self.lst.time, 0.0)
        np.testing.assert_almost_equal(
            self.lst.element['fluid_temperature'][-5:],
            [15.0, 15.0, 15.0, 15.0, 15.0]
            )

        self.lst.index = -1
        self.assertEqual(self.lst.index, 1)
        self.assertAlmostEqual(self.lst.time, 1.0E16)
        np.testing.assert_almost_equal(
            self.lst.element['fluid_temperature'][-5:],
            [235.7365710, 234.266913, 233.142164, 232.376319, 231.98525],
            decimal=4
            )

        ### generation
        np.testing.assert_almost_equal(
            self.lst.generation['source_rate'][:3],
            [0.075, 0.075, 160.0],
            decimal=4
            )
        np.testing.assert_almost_equal(
            self.lst.generation['source_enthalpy'][:3],
            [1200000.0, 1200000.0, 0.0],
            decimal=4
            )
        np.testing.assert_almost_equal(
            self.lst.generation['source_component'][:3],
            [1.0, 1.0, 2.0],
            decimal=4
            )

    def test_time(self):
        self.lst.time = self.lst.fulltimes[1] - 100.0
        self.assertEqual(self.lst.index, 1)
        self.lst.time = 1.0e19
        self.assertEqual(self.lst.index, 1)
        self.lst.time = 0.0
        self.assertEqual(self.lst.index, 0)
        self.lst.time = 100.0
        self.assertEqual(self.lst.index, 0)

    def test_history(self):
        # use relative tolerance, expect minor diff with different num of cpus
        rtol = 1e-10
        xs, ys = self.lst.history(('e', -1, 'fluid_pressure'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [101350.0, 1.3010923804323431E7], rtol=rtol)
        xs, ys = self.lst.history(('e', 339, 'fluid_pressure'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [101350.0, 1.3010923804323431E7], rtol=rtol)
        xs, ys = self.lst.history(('e', '  t16', 'fluid_pressure'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [101350.0, 1.3010923804323431E7], rtol=rtol)
        xs, ys = self.lst.history(('e', 338, 'fluid_temperature'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [15.0, 232.3763193900396], rtol=rtol)
        # cell index doesn't matter in generation
        xs, ys = self.lst.history(('g', (999, 0), 'source_enthalpy'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [1200e3, 1200e3], rtol=rtol)
        # also accepts single gener index int
        xs, ys = self.lst.history(('g', 0, 'source_enthalpy'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [1200e3, 1200e3], rtol=rtol)
        # also accepts gener index as str
        xs, ys = self.lst.history(('g', '0', 'source_enthalpy'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [1200e3, 1200e3], rtol=rtol)
        # cell index doesn't matter in generation
        xs, ys = self.lst.history(('g', (999, '0'), 'source_enthalpy'))
        np.testing.assert_allclose(xs, [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(ys, [1200e3, 1200e3], rtol=rtol)
        tbl = self.lst.history([
            ('e', -1, 'fluid_pressure'),
            ('e', 339, 'fluid_pressure'),
            ('e', '  t16', 'fluid_pressure'),
            ('e', 338, 'fluid_temperature'),
            ('g', (999, 0), 'source_enthalpy'),
            ])
        np.testing.assert_allclose(tbl[0][0], [0, 1.0e16], rtol=rtol)
        np.testing.assert_allclose(tbl[0][1], [101350.0, 1.3010923804323431E7], rtol=rtol)
        np.testing.assert_allclose(tbl[1][1], [101350.0, 1.3010923804323431E7], rtol=rtol)
        np.testing.assert_allclose(tbl[2][1], [101350.0, 1.3010923804323431E7], rtol=rtol)
        np.testing.assert_allclose(tbl[3][1], [15.0, 232.3763193900396], rtol=rtol)
        np.testing.assert_allclose(tbl[4][1], [1200e3, 1200e3], rtol=rtol)

        # should spit out an exception about not supporting atmosphere blocks
        self.assertRaises(Exception, self.lst.history, ('e', 0, 'fluid_temperature'))
        self.assertRaisesRegexp(Exception, 'atmosphere', self.lst.history, ('e', 0, 'fluid_temperature'))

class test_medium_multiple_cpu(test_medium):
    def setUp(self):
        from mulgrids import mulgrid
        self.geo = mulgrid('g2medium.dat')
        self.lst = wlisting('2DM002a.h5', self.geo)

class test_compare(unittest.TestCase):
    def setUp(self):
        from mulgrids import mulgrid
        self.geo = mulgrid('g2medium.dat')
        self.lst1 = wlisting('2DM002.h5', self.geo)
        self.lst2 = wlisting('2DM002a.h5', self.geo)

    def test_table(self):
        self.lst1.index = 1
        self.lst2.index = 1
        self.assertAlmostEqual(self.lst1.time, 1.0E16)
        self.assertAlmostEqual(self.lst2.time, 1.0E16)
        np.testing.assert_allclose(
            self.lst1.element['fluid_temperature'],
            self.lst2.element['fluid_temperature'],
            rtol=1e-10,
            equal_nan=True
            )
        np.testing.assert_allclose(
            self.lst1.element['fluid_pressure'],
            self.lst2.element['fluid_pressure'],
            rtol=1e-10,
            equal_nan=True
            )

    def test_history(self):
        np.testing.assert_allclose(
            self.lst1.history(('e', -1, 'fluid_pressure'))[1],
            self.lst2.history(('e', -1, 'fluid_pressure'))[1],
            rtol=1e-10,
            )
        np.testing.assert_allclose(
            self.lst1.history(('e', 128, 'fluid_temperature'))[1],
            self.lst2.history(('e', 128, 'fluid_temperature'))[1],
            rtol=1e-10,
            )

        # check for false positive, this should be different
        self.assertRaises(
            AssertionError,
            np.testing.assert_allclose,
            self.lst1.history(('e', 123, 'fluid_pressure'))[1],
            self.lst2.history(('e', 78, 'fluid_pressure'))[1],
            rtol=1e-10,
            )
        self.assertRaises(
            AssertionError,
            np.testing.assert_allclose,
            self.lst1.history(('e', 127, 'fluid_temperature'))[1],
            self.lst2.history(('e', 128, 'fluid_temperature'))[1],
            rtol=1e-10,
            )



if __name__ == '__main__':
    unittest.main(verbosity=2)

    # import time
    # from mulgrids import mulgrid
    # geo = mulgrid('gLihir_v7_NS.dat')
    # init_time = time.time()
    # lst = wlisting('Lihir_v7_SP_NS_060_wai.h5', geo)
    # print '%.2f sec' % (time.time() - init_time)
    # init_time = time.time()
    # lst.index = 1
    # print '%.2f sec' % (time.time() - init_time)



