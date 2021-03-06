#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#
# Analytical integration
# J. Chem. Phys. 65, 3826
# J. Chem. Phys. 111, 8778
# J. Comput. Phys. 44, 289
#
# Numerical integration
# J. Comput. Chem. 27, 1009
# Chem. Phys. Lett. 296, 445
#

import unittest
import numpy
from pyscf import gto
from pyscf import scf
from pyscf import lib


cu1_basis = gto.basis.parse('''
 H    S
       1.8000000              1.0000000
 H    S
       2.8000000              0.0210870             -0.0045400              0.0000000
       1.3190000              0.3461290             -0.1703520              0.0000000
       0.9059000              0.0393780              0.1403820              1.0000000
 H    P
       2.1330000              0.0868660              0.0000000
       1.2000000              0.0000000              0.5000000
       0.3827000              0.5010080              1.0000000
 H    D
       0.3827000              1.0000000
 H    F
       2.1330000              0.1868660              0.0000000
       0.3827000              0.2010080              1.0000000
                               ''')

mol = gto.M(atom='''
Cu1 0. 0. 0.
Cu 0. 1. 0.
He 1. 0. 0.
''',
            basis={'Cu':'lanl2dz', 'Cu1': cu1_basis, 'He':'sto3g'},
            ecp = {'cu':'lanl2dz'})

mol1 = gto.M(atom='''
Cu1 0.  0.  0.
Cu 0. 1. 0.
He 1. 0. 0.
Ghost-Cu1 0.  0.  0.0001
''',
             basis={'Cu':'lanl2dz', 'Cu1': cu1_basis, 'He':'sto3g'},
             ecp = {'cu':'lanl2dz'})

mol2 = gto.M(atom='''
Cu1 0.  0.  0.
Cu 0. 1. 0.
He 1. 0. 0.
Ghost-Cu1 0.  0. -0.0001
''',
             basis={'Cu':'lanl2dz', 'Cu1': cu1_basis, 'He':'sto3g'},
             ecp = {'cu':'lanl2dz'})

class KnowValues(unittest.TestCase):
    def test_nr_rhf(self):
        mol = gto.M(atom='Na 0. 0. 0.;  H  0.  0.  1.',
                    basis={'Na':'lanl2dz', 'H':'sto3g'},
                    ecp = {'Na':'lanl2dz'},
                    verbose=0)
        mf = scf.RHF(mol)
        self.assertAlmostEqual(mf.kernel(), -0.45002331958981223, 10)

    def test_bfd(self):
        mol = gto.M(atom='H 0. 0. 0.',
                    basis={'H':'bfd-vdz'},
                    ecp = {'H':'bfd-pp'},
                    spin = 1,
                    verbose=0)
        mf = scf.RHF(mol)
        self.assertAlmostEqual(mf.kernel(), -0.499045, 6)

        mol = gto.M(atom='Na 0. 0. 0.',
                    basis={'Na':'bfd-vtz'},
                    ecp = {'Na':'bfd-pp'},
                    spin = 1,
                    verbose=0)
        mf = scf.RHF(mol)
        self.assertAlmostEqual(mf.kernel(), -0.181799, 6)

        mol = gto.M(atom='Mg 0. 0. 0.',
                    basis={'Mg':'bfd-vtz'},
                    ecp = {'Mg':'bfd-pp'},
                    spin = 0,
                    verbose=0)
        mf = scf.RHF(mol)
        self.assertAlmostEqual(mf.kernel(), -0.784579, 6)

#        mol = gto.M(atom='Ne 0. 0. 0.',
#                    basis={'Ne':'bfd-vdz'},
#                    ecp = {'Ne':'bfd-pp'},
#                    verbose=0)
#        mf = scf.RHF(mol)
#        self.assertAlmostEqual(mf.kernel(), -34.709059, 6)

    def test_ecp_grad(self):
        aoslices = mol.aoslice_nr_by_atom()
        ish0, ish1 = aoslices[0][:2]
        for i in range(ish0, ish1):
            for j in range(mol.nbas):
                shls = (i,j)
                shls1 = (shls[0] + mol.nbas, shls[1])
                ref = (mol1.intor_by_shell('ECPscalar_cart', shls1) -
                       mol2.intor_by_shell('ECPscalar_cart', shls1)) / 0.0002 * lib.param.BOHR
                dat = mol.intor_by_shell('ECPscalar_ipnuc_cart', shls, comp=3)
                self.assertAlmostEqual(abs(-dat[2]-ref).max(), 0, 4)

    def test_ecp_hessian(self):
        aoslices = mol.aoslice_nr_by_atom()
        ish0, ish1 = aoslices[0][:2]
        for i in range(ish0, ish1):
            for j in range(mol.nbas):
                shls = (i,j)
                shls1 = (shls[0] + mol.nbas, shls[1])
                ref =-(mol1.intor_by_shell('ECPscalar_ipnuc_cart', shls1, comp=3) -
                       mol2.intor_by_shell('ECPscalar_ipnuc_cart', shls1, comp=3)) / 0.0002 * lib.param.BOHR
                dat = mol.intor_by_shell('ECPscalar_ipipnuc_cart', shls, comp=9)
                di, dj = dat.shape[1:]
                dat = dat.reshape(3,3,di,dj)
                self.assertAlmostEqual(abs(dat[2]-ref).max(), 0, 3)

        for i in range(mol.nbas):
            for j in range(ish0, ish1):
                shls = (i,j)
                shls1 = (shls[0], shls[1] + mol.nbas)
                ref =-(mol1.intor_by_shell('ECPscalar_ipnuc_cart', shls1, comp=3) -
                       mol2.intor_by_shell('ECPscalar_ipnuc_cart', shls1, comp=3)) / 0.0002 * lib.param.BOHR
                dat = mol.intor_by_shell('ECPscalar_ipnucip_cart', shls, comp=9)
                di, dj = dat.shape[1:]
                dat = dat.reshape(3,3,di,dj)
                self.assertAlmostEqual(abs(dat[:,2]-ref).max(), 0, 3)


if __name__ == '__main__':
    print("Full Tests for ECP")
    unittest.main()

