#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

import unittest
import numpy
import pyscf.pbc.gto as pbcgto
import pyscf.pbc.scf as pscf
cell = pbcgto.Cell()
cell.atom = '''
He 0 0 1
He 1 0 1
'''
cell.basis = '3-21g'
cell.a = numpy.eye(3) * 2
cell.mesh = [15] * 3
cell.verbose = 5
cell.output = '/dev/null'
cell.build()
nao = cell.nao_nr()

class KnowValues(unittest.TestCase):
    def test_krhf_smearing(self):
        mf = pscf.KRHF(cell, cell.make_kpts([2,1,1]))
        nkpts = len(mf.kpts)
        pscf.addons.smearing_(mf, 0.1, 'fermi')
        mo_energy_kpts = numpy.array([numpy.arange(nao)*.2+numpy.cos(i+.5)*.1
                                      for i in range(nkpts)])
        occ = mf.get_occ(mo_energy_kpts)
        self.assertAlmostEqual(mf.entropy, 6.1656394960533021/2, 9)

        mf.smearing_method = 'gauss'
        occ = mf.get_occ(mo_energy_kpts)
        self.assertAlmostEqual(mf.entropy, 0.94924016074521311/2, 9)

    def test_kuhf_smearing(self):
        mf = pscf.KUHF(cell, cell.make_kpts([2,1,1]))
        nkpts = len(mf.kpts)
        pscf.addons.smearing_(mf, 0.1, 'fermi')
        mo_energy_kpts = numpy.array([numpy.arange(nao)*.2+numpy.cos(i+.5)*.1
                                      for i in range(nkpts)])
        mo_energy_kpts = numpy.array([mo_energy_kpts,
                                      mo_energy_kpts+numpy.cos(mo_energy_kpts)*.02])
        occ = mf.get_occ(mo_energy_kpts)
        self.assertAlmostEqual(mf.entropy, 6.1803390081500869/2, 9)

        mf.smearing_method = 'gauss'
        occ = mf.get_occ(mo_energy_kpts)
        self.assertAlmostEqual(mf.entropy, 0.9554526863670467/2, 9)

    def test_rhf_smearing(self):
        mf = pscf.RHF(cell)
        pscf.addons.smearing_(mf, 0.1, 'fermi')
        mo_energy = numpy.arange(nao)*.2+numpy.cos(.5)*.1
        mf.get_occ(mo_energy)
        self.assertAlmostEqual(mf.entropy, 3.0922723199786408, 9)

        mf.smearing_method = 'gauss'
        occ = mf.get_occ(mo_energy)
        self.assertAlmostEqual(mf.entropy, 0.4152467504725415, 9)

    def test_uhf_smearing(self):
        mf = pscf.UHF(cell)
        pscf.addons.smearing_(mf, 0.1, 'fermi')
        mo_energy = numpy.arange(nao)*.2+numpy.cos(.5)*.1
        mo_energy = numpy.array([mo_energy, mo_energy+numpy.cos(mo_energy)*.02])
        mf.get_occ(mo_energy)
        self.assertAlmostEqual(mf.entropy, 3.1007387905421022, 9)

        mf.smearing_method = 'gauss'
        occ = mf.get_occ(mo_energy)
        self.assertAlmostEqual(mf.entropy, 0.42189309944541731, 9)

    def test_convert_to_rhf(self):
        cell = pbcgto.Cell()
        cell.atom = '''He 0 0 1; He 1 0 1'''
        cell.a = numpy.eye(3) * 3
        cell.mesh = [4] * 3
        cell.build()
        nks = [2,1,1]
        mf = pscf.KUHF(cell, cell.make_kpts(nks)).run()
        mf1 = pscf.addons.convert_to_rhf(mf)
        self.assertTrue(mf1.__class__ == pscf.khf.KRHF)

    def test_convert_to_uhf(self):
        cell = pbcgto.Cell()
        cell.atom = '''He 0 0 1; He 1 0 1'''
        cell.a = numpy.eye(3) * 3
        cell.mesh = [4] * 3
        cell.build()
        nks = [2,1,1]
        mf = pscf.KRHF(cell, cell.make_kpts(nks)).run()
        mf1 = pscf.addons.convert_to_uhf(mf)
        self.assertTrue(mf1.__class__ == pscf.kuhf.KUHF)

    def test_convert_to_scf(self):
        from pyscf.pbc import dft
        from pyscf.soscf import newton_ah
        cell1 = cell.copy()
        cell1.verbose = 0
        pscf.addons.convert_to_rhf(dft.RKS(cell1))
        pscf.addons.convert_to_uhf(dft.RKS(cell1))
        #pscf.addons.convert_to_ghf(dft.RKS(cell1))
        pscf.addons.convert_to_rhf(dft.UKS(cell1))
        pscf.addons.convert_to_uhf(dft.UKS(cell1))
        #pscf.addons.convert_to_ghf(dft.UKS(cell1))
        #pscf.addons.convert_to_rhf(dft.GKS(cell1))
        #pscf.addons.convert_to_uhf(dft.GKS(cell1))
        #pscf.addons.convert_to_ghf(dft.GKS(cell1))

        pscf.addons.convert_to_rhf(pscf.RHF(cell1).density_fit())
        pscf.addons.convert_to_uhf(pscf.RHF(cell1).density_fit())
        pscf.addons.convert_to_ghf(pscf.RHF(cell1).density_fit())
        pscf.addons.convert_to_rhf(pscf.UHF(cell1).density_fit())
        pscf.addons.convert_to_uhf(pscf.UHF(cell1).density_fit())
        pscf.addons.convert_to_ghf(pscf.UHF(cell1).density_fit())
        #pscf.addons.convert_to_rhf(pscf.GHF(cell1).density_fit())
        #pscf.addons.convert_to_uhf(pscf.GHF(cell1).density_fit())
        pscf.addons.convert_to_ghf(pscf.GHF(cell1).density_fit())

        pscf.addons.convert_to_rhf(pscf.RHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_uhf(pscf.RHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_ghf(pscf.RHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_rhf(pscf.UHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_uhf(pscf.UHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_ghf(pscf.UHF(cell1).x2c().density_fit())
        #pscf.addons.convert_to_rhf(pscf.GHF(cell1).x2c().density_fit())
        #pscf.addons.convert_to_uhf(pscf.GHF(cell1).x2c().density_fit())
        pscf.addons.convert_to_ghf(pscf.GHF(cell1).x2c().density_fit())

        self.assertTrue (isinstance(pscf.addons.convert_to_rhf(pscf.RHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertFalse(isinstance(pscf.addons.convert_to_uhf(pscf.RHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertFalse(isinstance(pscf.addons.convert_to_ghf(pscf.RHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertFalse(isinstance(pscf.addons.convert_to_rhf(pscf.UHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertTrue (isinstance(pscf.addons.convert_to_uhf(pscf.UHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertFalse(isinstance(pscf.addons.convert_to_ghf(pscf.UHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        #self.assertFalse(isinstance(pscf.addons.convert_to_rhf(pscf.GHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        #self.assertFalse(isinstance(pscf.addons.convert_to_uhf(pscf.GHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))
        self.assertTrue (isinstance(pscf.addons.convert_to_ghf(pscf.GHF(cell1).newton().density_fit().x2c()), newton_ah._CIAH_SOSCF))


if __name__ == '__main__':
    print("Full Tests for pbc.scf.addons")
    unittest.main()
