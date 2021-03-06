#!/usr/bin/env python

import unittest
import numpy
from pyscf import gto, scf, lib
from pyscf import grad

mol = gto.Mole()
mol.verbose = 5
mol.output = '/dev/null'
mol.atom.extend([
    ["O" , (0. , 0.     , 0.)],
    [1   , (0. , -0.757 , 0.587)],
    [1   , (0. , 0.757  , 0.587)] ])
mol.basis = '6-31g'
mol.build()


def make_mol(atom_id, coords):
    mol1 = mol.copy()
    mol1.atom[atom_id] = [mol1.atom[atom_id][0], coords]
    mol1.build(0, 0)
    return mol1

class KnownValues(unittest.TestCase):
    def test_finite_diff_x2c_rhf_grad(self):
        mf = scf.RHF(mol).x2c()
        mf.conv_tol = 1e-14
        e0 = mf.kernel()
        g = grad.RHF(mf).kernel()
        self.assertAlmostEqual(lib.finger(g), 0.0056363502746766807, 6)

        mf_scanner = mf.as_scanner()

        e1 = mf_scanner(make_mol(0, (0, 0, 1e-4)))
        e2 = mf_scanner(make_mol(0, (0, 0,-1e-4)))
        self.assertAlmostEqual(g[0,2], (e1-e2)/2e-4*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(0, (0, 1e-5, 0)))
        e2 = mf_scanner(make_mol(0, (0,-1e-5, 0)))
        self.assertAlmostEqual(g[0,1], (e1-e2)/2e-5*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(1, (0. , -0.7571 , 0.587)))
        e2 = mf_scanner(make_mol(1, (0. , -0.7569 , 0.587)))
        self.assertAlmostEqual(g[1,1], (e2-e1)/2e-4*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(1, (0. , -0.757 , 0.5871)))
        e2 = mf_scanner(make_mol(1, (0. , -0.757 , 0.5869)))
        self.assertAlmostEqual(g[1,2], (e1-e2)/2e-4*lib.param.BOHR, 5)

    def test_finite_diff_rhf_grad(self):
        mf = scf.RHF(mol)
        mf.conv_tol = 1e-14
        e0 = mf.kernel()
        g = grad.RHF(mf).kernel()
        self.assertAlmostEqual(lib.finger(g), 0.0055115512502467556, 6)
        mf_scanner = mf.as_scanner()

        e1 = mf_scanner(make_mol(0, (0, 0, 1e-4)))
        e2 = mf_scanner(make_mol(0, (0, 0,-1e-4)))
        self.assertAlmostEqual(g[0,2], (e1-e2)/2e-4*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(0, (0, 1e-5, 0)))
        e2 = mf_scanner(make_mol(0, (0,-1e-5, 0)))
        self.assertAlmostEqual(g[0,1], (e1-e2)/2e-5*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(1, (0. , -0.7571 , 0.587)))
        e2 = mf_scanner(make_mol(1, (0. , -0.7569 , 0.587)))
        self.assertAlmostEqual(g[1,1], (e2-e1)/2e-4*lib.param.BOHR, 5)

        e1 = mf_scanner(make_mol(1, (0. , -0.757 , 0.5871)))
        e2 = mf_scanner(make_mol(1, (0. , -0.757 , 0.5869)))
        self.assertAlmostEqual(g[1,2], (e1-e2)/2e-4*lib.param.BOHR, 5)


if __name__ == "__main__":
    print("Full Tests for RHF Gradients")
    unittest.main()

