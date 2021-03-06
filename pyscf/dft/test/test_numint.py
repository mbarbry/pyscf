#!/usr/bin/env python

import unittest
import numpy
from pyscf import gto
from pyscf import dft
from pyscf import lib

dft.numint.SWITCH_SIZE = 0

mol = gto.Mole()
mol.verbose = 0
mol.atom = [('h', (0,0,i*3)) for i in range(12)]
mol.basis = 'ccpvtz'
mol.build()
mf = dft.RKS(mol)
mf.grids.atom_grid = {"H": (50, 110)}
mf.prune = None
mf.grids.build(with_non0tab=False)
nao = mol.nao_nr()
ao_loc = mol.ao_loc_nr()

h4 = gto.Mole()
h4.verbose = 0
h4.atom = 'H 0 0 0; H 0 0 9; H 0 9 0; H 0 9 9'
h4.basis = 'ccpvtz'
h4.build()
mf_h4 = dft.RKS(h4)
mf_h4.grids.atom_grid = {"H": (50, 110)}
mf_h4.grids.build(with_non0tab=True)

mol1 = gto.Mole()
mol1.verbose = 0
mol1.atom = [('h', (0,0,i*3)) for i in range(4)]
mol1.basis = 'ccpvtz'
mol1.build()

h2o = gto.Mole()
h2o.verbose = 5
h2o.output = '/dev/null'
h2o.atom = [
    ["O" , (0. , 0.     , 0.)],
    [1   , (0. , -0.757 , 0.587)],
    [1   , (0. , 0.757  , 0.587)] ]

h2o.basis = {"H": '6-31g', "O": '6-31g',}
h2o.build()

def finger(a):
    return numpy.dot(numpy.cos(numpy.arange(a.size)), a.ravel())

class KnownValues(unittest.TestCase):
    def test_make_mask(self):
        non0 = dft.numint.make_mask(mol, mf.grids.coords)
        self.assertEqual(non0.sum(), 10244)
        self.assertAlmostEqual(finger(non0), -2.6880474684794895, 9)
        self.assertAlmostEqual(finger(numpy.cos(non0)), 2.5961863522983433, 9)

    def test_dot_ao_dm(self):
        non0tab = mf._numint.make_mask(mol, mf.grids.coords)
        ao = dft.numint.eval_ao(mol, mf.grids.coords)
        numpy.random.seed(1)
        nao = ao.shape[1]
        ao_loc = mol.ao_loc_nr()
        dm = numpy.random.random((nao,nao))
        dm = dm + dm.T
        res0 = lib.dot(ao, dm)
        res1 = dft.numint._dot_ao_dm(mol, ao, dm, non0tab,
                                     shls_slice=(0,mol.nbas), ao_loc=ao_loc)
        self.assertTrue(numpy.allclose(res0, res1))

        dm = mf_h4.get_init_guess(key='minao')
        ao_loc = h4.ao_loc_nr()
        ao = mf_h4._numint.eval_ao(h4, mf_h4.grids.coords).copy() + 0j
        nao = ao.shape[1]
        v1 = dft.numint._dot_ao_dm(h4, ao, dm, mf_h4.grids.non0tab, (0,h4.nbas), ao_loc)
        v2 = dft.numint._dot_ao_dm(h4, ao, dm, None, None, None)
        self.assertAlmostEqual(abs(v1-v2).max(), 0, 9)

    def test_dot_ao_ao(self):
        non0tab = mf.grids.make_mask(mol, mf.grids.coords)
        ao = dft.numint.eval_ao(mol, mf.grids.coords, deriv=1)
        nao = ao.shape[1]
        ao_loc = mol.ao_loc_nr()
        res0 = lib.dot(ao[0].T, ao[1])
        res1 = dft.numint._dot_ao_ao(mol, ao[0], ao[1], non0tab,
                                     shls_slice=(0,mol.nbas), ao_loc=ao_loc)
        self.assertTrue(numpy.allclose(res0, res1))

        dm = mf_h4.get_init_guess(key='minao')
        ao_loc = h4.ao_loc_nr()
        ao = mf_h4._numint.eval_ao(h4, mf_h4.grids.coords).copy() + 0j
        nao = h4.nao_nr()
        v1 = dft.numint._dot_ao_ao(h4, ao, ao, mf_h4.grids.non0tab, (0,h4.nbas), ao_loc)
        v2 = dft.numint._dot_ao_ao(h4, ao, ao, None, None, None)
        self.assertAlmostEqual(abs(v1-v2).max(), 0, 9)

    def test_eval_rho(self):
        numpy.random.seed(10)
        ngrids = 500
        coords = numpy.random.random((ngrids,3))*20
        dm = numpy.random.random((nao,nao))
        dm = dm + dm.T
        ao = dft.numint.eval_ao(mol, coords, deriv=2)

        e, mo_coeff = numpy.linalg.eigh(dm)
        mo_occ = numpy.ones(nao)
        mo_occ[-2:] = -1
        dm = numpy.einsum('pi,i,qi->pq', mo_coeff, mo_occ, mo_coeff)

        rho0 = numpy.zeros((6,ngrids))
        rho0[0] = numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[0].conj())
        rho0[1] = numpy.einsum('pi,ij,pj->p', ao[1], dm, ao[0].conj()) + numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[1].conj())
        rho0[2] = numpy.einsum('pi,ij,pj->p', ao[2], dm, ao[0].conj()) + numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[2].conj())
        rho0[3] = numpy.einsum('pi,ij,pj->p', ao[3], dm, ao[0].conj()) + numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[3].conj())
        rho0[4]+= numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[4].conj()) + numpy.einsum('pi,ij,pj->p', ao[4], dm, ao[0].conj())
        rho0[4]+= numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[7].conj()) + numpy.einsum('pi,ij,pj->p', ao[7], dm, ao[0].conj())
        rho0[4]+= numpy.einsum('pi,ij,pj->p', ao[0], dm, ao[9].conj()) + numpy.einsum('pi,ij,pj->p', ao[9], dm, ao[0].conj())
        rho0[5]+= numpy.einsum('pi,ij,pj->p', ao[1], dm, ao[1].conj())
        rho0[5]+= numpy.einsum('pi,ij,pj->p', ao[2], dm, ao[2].conj())
        rho0[5]+= numpy.einsum('pi,ij,pj->p', ao[3], dm, ao[3].conj())
        rho0[4]+= rho0[5]*2
        rho0[5] *= .5

        ni = dft.numint._NumInt()
        rho1 = ni.eval_rho (mol, ao, dm, xctype='MGGA')
        rho2 = ni.eval_rho2(mol, ao, mo_coeff, mo_occ, xctype='MGGA')
        self.assertTrue(numpy.allclose(rho0, rho1))
        self.assertTrue(numpy.allclose(rho0, rho2))

    def test_eval_mat(self):
        numpy.random.seed(10)
        ngrids = 500
        coords = numpy.random.random((ngrids,3))*20
        rho = numpy.random.random((6,ngrids))
        vxc = numpy.random.random((4,ngrids))
        weight = numpy.random.random(ngrids)
        ao = dft.numint.eval_ao(mol, coords, deriv=2)

        mat0 = numpy.einsum('pi,p,pj->ij', ao[0].conj(), weight*vxc[0], ao[0])
        mat1 = dft.numint.eval_mat(mol, ao[0], weight, rho, vxc[0], xctype='LDA')
        self.assertTrue(numpy.allclose(mat0, mat1))
        # UKS
        mat2 = dft.numint.eval_mat(mol, ao[0], weight, rho, [vxc[0]]*2, xctype='LDA', spin=1)
        self.assertTrue(numpy.allclose(mat0, mat2))

        vrho, vsigma = vxc[:2]
        wv = weight * vsigma * 2
        mat0  = numpy.einsum('pi,p,pj->ij', ao[0].conj(), weight*vrho, ao[0])
        mat0 += numpy.einsum('pi,p,pj->ij', ao[0].conj(), rho[1]*wv, ao[1]) + numpy.einsum('pi,p,pj->ij', ao[1].conj(), rho[1]*wv, ao[0])
        mat0 += numpy.einsum('pi,p,pj->ij', ao[0].conj(), rho[2]*wv, ao[2]) + numpy.einsum('pi,p,pj->ij', ao[2].conj(), rho[2]*wv, ao[0])
        mat0 += numpy.einsum('pi,p,pj->ij', ao[0].conj(), rho[3]*wv, ao[3]) + numpy.einsum('pi,p,pj->ij', ao[3].conj(), rho[3]*wv, ao[0])
        mat1 = dft.numint.eval_mat(mol, ao, weight, rho, vxc[:4], xctype='GGA')
        self.assertTrue(numpy.allclose(mat0, mat1))
        # UKS
        vxc_1 = [vxc[0], (vxc[1], 0)]
        mat2 = dft.numint.eval_mat(mol, ao, weight, [rho[:4]]*2, vxc_1, xctype='GGA', spin=1)
        self.assertTrue(numpy.allclose(mat0, mat2))

        vrho, vsigma, _, vtau = vxc
        vxc = (vrho, vsigma, None, vtau)
        wv = weight * vtau * .5
        mat2  = numpy.einsum('pi,p,pj->ij', ao[1].conj(), wv, ao[1])
        mat2 += numpy.einsum('pi,p,pj->ij', ao[2].conj(), wv, ao[2])
        mat2 += numpy.einsum('pi,p,pj->ij', ao[3].conj(), wv, ao[3])
        mat0 += mat2
        mat1 = dft.numint.eval_mat(mol, ao, weight, rho, vxc, xctype='MGGA')
        self.assertTrue(numpy.allclose(mat0, mat1))
        # UKS
        vxc_1 = [vxc[0], (vxc[1], 0), (0,0), (vxc[3],0)]
        mat2 = dft.numint.eval_mat(mol, ao, weight, [rho]*2, vxc_1, xctype='MGGA', spin=1)
        self.assertTrue(numpy.allclose(mat0, mat2))

    def test_rks_vxc(self):
        numpy.random.seed(10)
        nao = mol.nao_nr()
        dms = numpy.random.random((2,nao,nao))
        v = mf._numint.nr_vxc(mol, mf.grids, 'B88', dms, spin=0, hermi=0)[2]
        self.assertAlmostEqual(finger(v), -0.70124686853021512, 8)

    def test_uks_vxc(self):
        numpy.random.seed(10)
        nao = mol.nao_nr()
        dms = numpy.random.random((2,nao,nao))
        v = mf._numint.nr_vxc(mol, mf.grids, 'B88', dms, spin=1)[2]
        self.assertAlmostEqual(finger(v), -0.73803886056633594, 8)

    def test_rks_fxc(self):
        numpy.random.seed(10)
        nao = mol1.nao_nr()
        dm0 = numpy.random.random((nao,nao))
        _, mo_coeff = numpy.linalg.eigh(dm0)
        mo_occ = numpy.ones(nao)
        mo_occ[-2:] = -1
        dm0 = numpy.einsum('pi,i,qi->pq', mo_coeff, mo_occ, mo_coeff)
        dms = numpy.random.random((2,nao,nao))
        ni = dft.numint._NumInt()
        v = ni.nr_fxc(mol1, mf.grids, 'B88', dm0, dms, spin=0, hermi=0)
        self.assertAlmostEqual(finger(v), -7.5671368618070343, 8)

        # test cache_kernel
        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'B88', mo_coeff, mo_occ, spin=0)
        v1 = dft.numint.nr_fxc(mol1, mf.grids, 'B88', dm0, dms, spin=0, hermi=0,
                               rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

        v = ni.nr_fxc(mol1, mf.grids, 'LDA', dm0, dms[0], spin=0, hermi=0)
        self.assertAlmostEqual(finger(v), -3.0019207112626876, 8)
        # test cache_kernel
        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'LDA', mo_coeff, mo_occ, spin=0)
        v1 = dft.numint.nr_fxc(mol1, mf.grids, 'LDA', dm0, dms[0], spin=0, hermi=0,
                               rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

    def test_rks_fxc_st(self):
        numpy.random.seed(10)
        nao = mol1.nao_nr()
        dm0 = numpy.random.random((nao,nao))
        _, mo_coeff = numpy.linalg.eigh(dm0)
        mo_occ = numpy.ones(nao)
        mo_occ[-2:] = -1
        dm0 = numpy.einsum('pi,i,qi->pq', mo_coeff, mo_occ, mo_coeff)
        dms = numpy.random.random((2,nao,nao))
        ni = dft.numint._NumInt()

        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'B88', [mo_coeff,mo_coeff],
                                 [mo_occ*.5]*2, spin=1)
        v = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'B88', dm0, dms, singlet=True)
        self.assertAlmostEqual(finger(v), -7.5671368618070343*2, 8)
        v1 = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'B88', dm0, dms, singlet=True,
                                      rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

        v = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'B88', dm0, dms, singlet=False)
        self.assertAlmostEqual(finger(v), -7.5671368618070343*2, 8)
        v1 = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'B88', dm0, dms, singlet=False,
                                      rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'LDA', [mo_coeff,mo_coeff],
                                 [mo_occ*.5]*2, spin=1)
        v = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'LDA', dm0, dms[0], singlet=True)
        self.assertAlmostEqual(finger(v), -3.0019207112626876*2, 8)
        v1 = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'LDA', dm0, dms[0], singlet=True,
                                      rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

        v = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'LDA', dm0, dms[0], singlet=False)
        self.assertAlmostEqual(finger(v), -3.0019207112626876*2, 8)
        v1 = dft.numint.nr_rks_fxc_st(ni, mol1, mf.grids, 'LDA', dm0, dms[0], singlet=False,
                                      rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

    def test_uks_fxc(self):
        numpy.random.seed(10)
        nao = mol1.nao_nr()
        dm0 = numpy.random.random((2,nao,nao))
        e, mo_coeff = numpy.linalg.eigh(dm0)
        mo_occ = numpy.ones((2,nao))
        mo_occ[:,-2:] = -1
        dm0 = numpy.einsum('xpi,xi,xqi->xpq', mo_coeff, mo_occ, mo_coeff)
        dms = numpy.random.random((2,nao,nao))
        ni = dft.numint._NumInt()
        v = ni.nr_fxc(mol1, mf.grids, 'B88', dm0, dms, spin=1)
        self.assertAlmostEqual(finger(v), -10.316443204083185, 8)

        # test cache_kernel
        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'B88', mo_coeff, mo_occ, spin=1)
        v1 = dft.numint.nr_fxc(mol1, mf.grids, 'B88', dm0, dms, hermi=0, spin=1,
                               rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

        v = ni.nr_fxc(mol1, mf.grids, 'LDA', dm0, dms[0], spin=1)
        self.assertAlmostEqual(finger(v), -5.6474405864697967, 8)
        # test cache_kernel
        rvf = ni.cache_xc_kernel(mol1, mf.grids, 'LDA', mo_coeff, mo_occ, spin=1)
        v1 = dft.numint.nr_fxc(mol1, mf.grids, 'LDA', dm0, dms[0], hermi=0, spin=1,
                               rho0=rvf[0], vxc=rvf[1], fxc=rvf[2])
        self.assertAlmostEqual(abs(v-v1).max(), 0, 8)

    def test_vv10nlc(self):
        numpy.random.seed(10)
        rho = numpy.random.random((4,20))
        coords = (numpy.random.random((20,3))-.5)*3
        vvrho = numpy.random.random((4,60))
        vvweight = numpy.random.random(60)
        vvcoords = (numpy.random.random((60,3))-.5)*3
        nlc_pars = .8, .3
        v = dft.numint._vv10nlc(rho, coords, vvrho, vvweight, vvcoords, nlc_pars)
        self.assertAlmostEqual(finger(v[0]), 0.15894647203764295, 9)
        self.assertAlmostEqual(finger(v[1]), 0.20500922537924576, 9)

    def test_nr_uks_vxc_vv10(self):
        method = dft.UKS(h2o)
        dm = method.get_init_guess()
        dm = (dm[0], dm[0])
        grids = dft.gen_grid.Grids(h2o)
        grids.atom_grid = {'H': (20, 50), 'O': (20,50)}
        v = dft.numint.nr_vxc(h2o, grids, 'wB97M_V__vv10', dm, spin=1, hermi=0)[2]
        self.assertAlmostEqual(finger(v), 0.02293399033256055, 8)


if __name__ == "__main__":
    print("Test numint")
    unittest.main()

