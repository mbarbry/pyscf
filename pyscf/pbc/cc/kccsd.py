#!/usr/bin/env python
#
# Authors: James D. McClain <jmcclain@princeton.edu>
#          Timothy Berkelbach <tim.berkelbach@gmail.com>
#

import time
import numpy
from functools import reduce

from pyscf import lib
from pyscf.lib import logger
from pyscf.pbc import scf
from pyscf.cc import gccsd
from pyscf.pbc.cc import kintermediates as imdk
from pyscf.pbc.lib import kpts_helper

DEBUG = False

#
#FIXME: When linear dependence is found in KHF and handled by function
# pyscf.scf.addons.remove_linear_dep_, different k-point may have different
# number of orbitals.
#

#einsum = np.einsum
einsum = lib.einsum

def kernel(cc, eris, t1=None, t2=None, max_cycle=50, tol=1e-8, tolnormt=1e-6,
           max_memory=2000, verbose=logger.INFO):
    """Exactly the same as pyscf.cc.ccsd.kernel, which calls a
    *local* energy() function."""
    if isinstance(verbose, logger.Logger):
        log = verbose
    else:
        log = logger.Logger(cc.stdout, verbose)

    assert(isinstance(eris, gccsd._PhysicistsERIs))
    if t1 is None and t2 is None:
        t1, t2 = cc.init_amps(eris)[1:]
    elif t1 is None:
        nocc = cc.get_nocc()
        nvir = cc.get_nmo() - nocc
        nkpts = cc.nkpts
        t1 = numpy.zeros((nkpts,nocc,nvir), numpy.complex128)
    elif t2 is None:
        t2 = cc.init_amps(eris)[2]

    cput1 = cput0 = (time.clock(), time.time())
    nkpts, nocc, nvir = t1.shape
    eold = 0
    eccsd = 0

    if cc.diis:
        adiis = lib.diis.DIIS(cc, cc.diis_file)
        adiis.space = cc.diis_space
    else:
        adiis = lambda t1,t2,*args: (t1,t2)

    conv = False
    for istep in range(max_cycle):
        t1new, t2new = cc.update_amps(t1, t2, eris, max_memory)
        normt = numpy.linalg.norm(t1new-t1) + numpy.linalg.norm(t2new-t2)
        t1, t2 = t1new, t2new
        t1new = t2new = None

        if cc.diis:
            t1, t2 = cc.diis(t1, t2, istep, normt, eccsd-eold, adiis)
        eold, eccsd = eccsd, energy(cc, t1, t2, eris)
        log.info('istep = %d  E(CCSD) = %.15g  dE = %.9g  norm(t1,t2) = %.6g',
                 istep, eccsd, eccsd - eold, normt)
        cput1 = log.timer('CCSD iter', *cput1)
        if abs(eccsd-eold) < tol and normt < tolnormt:
            conv = True
            break
    log.timer('CCSD', *cput0)
    return conv, eccsd, t1, t2

def energy(cc, t1, t2, eris):
    nkpts, nocc, nvir = t1.shape
    fock = eris.fock
    eris_oovv = eris.oovv.copy()
    e = 0.0 + 0j
    for ki in range(nkpts):
        e += einsum('ia,ia', fock[ki,:nocc,nocc:], t1[ki,:,:])
    t1t1 = numpy.zeros(shape=t2.shape,dtype=t2.dtype)
    for ki in range(nkpts):
        ka = ki
        for kj in range(nkpts):
            #kb = kj
            t1t1[ki,kj,ka,:,:,:,:] = einsum('ia,jb->ijab',t1[ki,:,:],t1[kj,:,:])
    tau = t2 + 2*t1t1
    e += 0.25 * numpy.dot(tau.flatten(), eris_oovv.flatten())
    e /= nkpts
    return e.real

def update_amps(cc, t1, t2, eris, max_memory=2000):
    time0 = time.clock(), time.time()
    log = logger.Logger(cc.stdout, cc.verbose)
    nkpts, nocc, nvir = t1.shape
    fock = eris.fock

    fov = fock[:,:nocc,nocc:].copy()
    foo = fock[:,:nocc,:nocc].copy()
    fvv = fock[:,nocc:,nocc:].copy()

    #mo_e = eris.fock.diagonal()
    #eia = mo_e[:nocc,None] - mo_e[None,nocc:]
    #eijab = lib.direct_sum('ia,jb->ijab',eia,eia)

    tau = imdk.make_tau(cc,t2,t1,t1)

    Fvv = imdk.cc_Fvv(cc,t1,t2,eris)
    Foo = imdk.cc_Foo(cc,t1,t2,eris)
    Fov = imdk.cc_Fov(cc,t1,t2,eris)
    Woooo = imdk.cc_Woooo(cc,t1,t2,eris)
    Wvvvv = imdk.cc_Wvvvv(cc,t1,t2,eris)
    Wovvo = imdk.cc_Wovvo(cc,t1,t2,eris)

    # Move energy terms to the other side
    for k in range(nkpts):
        Fvv[k] -= numpy.diag(numpy.diag(fvv[k]))
        Foo[k] -= numpy.diag(numpy.diag(foo[k]))

    # Get the momentum conservation array
    # Note: chemist's notation for momentum conserving t2(ki,kj,ka,kb), even though
    # integrals are in physics notation
    kconserv = kpts_helper.get_kconserv(cc._scf.cell, cc.kpts)

    eris_ovvo = numpy.zeros(shape=(nkpts,nkpts,nkpts,nocc,nvir,nvir,nocc), dtype=t2.dtype)
    eris_oovo = numpy.zeros(shape=(nkpts,nkpts,nkpts,nocc,nocc,nvir,nocc), dtype=t2.dtype)
    eris_vvvo = numpy.zeros(shape=(nkpts,nkpts,nkpts,nvir,nvir,nvir,nocc), dtype=t2.dtype)
    for km, kb, ke in kpts_helper.loop_kkk(nkpts):
        kj = kconserv[km,ke,kb]
        # <mb||je> -> -<mb||ej>
        eris_ovvo[km,kb,ke] = -eris.ovov[km,kb,kj].transpose(0,1,3,2)
        # <mn||je> -> -<mn||ej>
        # let kb = kn as a dummy variable
        eris_oovo[km,kb,ke] = -eris.ooov[km,kb,kj].transpose(0,1,3,2)
        # <ma||be> -> - <be||am>*
        # let kj = ka as a dummy variable
        kj = kconserv[km,ke,kb]
        eris_vvvo[ke,kj,kb] = -eris.ovvv[km,kb,ke].transpose(2,3,1,0).conj()

    # T1 equation
    t1new = numpy.zeros(shape=t1.shape, dtype=t1.dtype)
    for ka in range(nkpts):
        ki = ka
        t1new[ka] += numpy.array(fov[ka,:,:]).conj()
        t1new[ka] +=  einsum('ie,ae->ia',t1[ka],Fvv[ka])
        t1new[ka] += -einsum('ma,mi->ia',t1[ka],Foo[ka])
        for km in range(nkpts):
            t1new[ka] +=  einsum('imae,me->ia',t2[ka,km,ka],Fov[km])
            t1new[ka] += -einsum('nf,naif->ia',t1[km],eris.ovov[km,ka,ki])
            for kn in range(nkpts):
                ke = kconserv[km,ki,kn]
                t1new[ka] += -0.5*einsum('imef,maef->ia',t2[ki,km,ke],eris.ovvv[km,ka,ke])
                t1new[ka] += -0.5*einsum('mnae,nmei->ia',t2[km,kn,ka],eris_oovo[kn,km,ke])

    # T2 equation
    t2new = numpy.array(eris.oovv).conj()
    for ki, kj, ka in kpts_helper.loop_kkk(nkpts):
        # Chemist's notation for momentum conserving t2(ki,kj,ka,kb)
        kb = kconserv[ki,ka,kj]

        Ftmp = Fvv[kb] - 0.5*einsum('mb,me->be',t1[kb],Fov[kb])
        tmp = einsum('ijae,be->ijab',t2[ki,kj,ka],Ftmp)
        t2new[ki,kj,ka] += tmp

        #t2new[ki,kj,kb] -= tmp.transpose(0,1,3,2)
        Ftmp = Fvv[ka] - 0.5*einsum('ma,me->ae',t1[ka],Fov[ka])
        tmp = einsum('ijbe,ae->ijab',t2[ki,kj,kb],Ftmp)
        t2new[ki,kj,ka] -= tmp

        Ftmp = Foo[kj] + 0.5*einsum('je,me->mj',t1[kj],Fov[kj])
        tmp = einsum('imab,mj->ijab',t2[ki,kj,ka],Ftmp)
        t2new[ki,kj,ka] -= tmp

        #t2new[kj,ki,ka] += tmp.transpose(1,0,2,3)
        Ftmp = Foo[ki] + 0.5*einsum('ie,me->mi',t1[ki],Fov[ki])
        tmp = einsum('jmab,mi->ijab',t2[kj,ki,ka],Ftmp)
        t2new[ki,kj,ka] += tmp

        for km in range(nkpts):
            # Wminj
            #   - km - kn + ka + kb = 0
            # =>  kn = ka - km + kb
            kn = kconserv[ka,km,kb]
            t2new[ki,kj,ka] += 0.5*einsum('mnab,mnij->ijab',tau[km,kn,ka],Woooo[km,kn,ki])
            ke = km
            t2new[ki,kj,ka] += 0.5*einsum('ijef,abef->ijab',tau[ki,kj,ke],Wvvvv[ka,kb,ke])

            # Wmbej
            #     - km - kb + ke + kj = 0
            #  => ke = km - kj + kb
            ke = kconserv[km,kj,kb]
            tmp = einsum('imae,mbej->ijab',t2[ki,km,ka],Wovvo[km,kb,ke])
            #     - km - kb + ke + kj = 0
            # =>  ke = km - kj + kb
            #
            # t[i,e] => ki = ke
            # t[m,a] => km = ka
            if km == ka and ke == ki:
                tmp -= einsum('ie,ma,mbej->ijab',t1[ki],t1[km],eris_ovvo[km,kb,ke])
            t2new[ki,kj,ka] += tmp
            t2new[ki,kj,kb] -= tmp.transpose(0,1,3,2)
            t2new[kj,ki,ka] -= tmp.transpose(1,0,2,3)
            t2new[kj,ki,kb] += tmp.transpose(1,0,3,2)

        ke = ki
        tmp = einsum('ie,abej->ijab',t1[ki],eris_vvvo[ka,kb,ke])
        t2new[ki,kj,ka] += tmp
        # P(ij) term
        ke = kj
        tmp = einsum('je,abei->ijab',t1[kj],eris_vvvo[ka,kb,ke])
        t2new[ki,kj,ka] -= tmp

        km = ka
        tmp = einsum('ma,mbij->ijab',t1[ka],eris.ovoo[km,kb,ki])
        t2new[ki,kj,ka] -= tmp
        # P(ab) term
        km = kb
        tmp = einsum('mb,maij->ijab',t1[kb],eris.ovoo[km,ka,ki])
        t2new[ki,kj,ka] += tmp

    eia = numpy.zeros(shape=t1new.shape, dtype=t1new.dtype)
    for ki in range(nkpts):
        for i in range(nocc):
            for a in range(nvir):
                eia[ki,i,a] = foo[ki,i,i] - fvv[ki,a,a]
        t1new[ki] /= eia[ki]

    eijab = numpy.zeros(shape=t2new.shape, dtype=t2new.dtype)
    kconserv = kpts_helper.get_kconserv(cc._scf.cell, cc.kpts)
    for ki, kj, ka in kpts_helper.loop_kkk(nkpts):
        kb = kconserv[ki,ka,kj]
        for i in range(nocc):
            for a in range(nvir):
                for j in range(nocc):
                    for b in range(nvir):
                        eijab[ki,kj,ka,i,j,a,b] = ( foo[ki,i,i] + foo[kj,j,j]
                                                  - fvv[ka,a,a] - fvv[kb,b,b] )
        t2new[ki,kj,ka] /= eijab[ki,kj,ka]

    time0 = log.timer_debug1('update t1 t2', *time0)

    return t1new, t2new


def get_nocc(cc):
    # Spin orbitals
    # TODO: Possibly change this to make it work with k-points with frozen
    #       As of right now it works, but just not sure how the frozen list will work
    #       with it
    if cc._nocc is not None:
        return cc._nocc
    elif isinstance(cc.frozen, (int, numpy.integer)):
        nocc = int(cc.mo_occ[0].sum()) - cc.frozen
    elif isinstance(cc.frozen[0], (int, numpy.integer)):
        nocc = int(cc.mo_occ[0].sum()) - len(cc.frozen)
    else:
        raise NotImplementedError
    return nocc

def get_nmo(cc):
    # TODO: Change this for frozen at k-points, seems like it should work
    if cc._nmo is not None:
        return cc._nmo
    elif isinstance(cc.frozen, (int, numpy.integer)):
        nmo = len(cc.mo_occ[0]) - cc.frozen
    elif isinstance(cc.frozen[0], (int, numpy.integer)):
        nmo = len(cc.mo_occ[0]) - len(cc.frozen)
    else:
        raise NotImplementedError
    return nmo


def get_frozen_mask(cc):
    moidx = [numpy.ones(x.size, dtype=numpy.bool) for x in cc.mo_occ]
    if isinstance(cc.frozen, (int, numpy.integer)):
        for idx in moidx:
            idx[:cc.frozen] = False
    elif isinstance(cc.frozen[0], (int, numpy.integer)):
        frozen = list(cc.frozen)
        for idx in moidx:
            idx[frozen] = False
    else:
        raise NotImplementedError
    return moidx


class GCCSD(gccsd.GCCSD):

    def __init__(self, mf, frozen=0, mo_coeff=None, mo_occ=None):
        assert(isinstance(mf, scf.khf.KSCF))
        if not isinstance(mf, scf.kghf.KGHF):
            mf = scf.addons.convert_to_ghf(mf)
        self.kpts = mf.kpts
        gccsd.GCCSD.__init__(self, mf, frozen, mo_coeff, mo_occ)

    @property
    def nkpts(self):
        return len(self.kpts)

    get_nocc = get_nocc
    get_nmo = get_nmo
    get_frozen_mask = get_frozen_mask

    def dump_flags(self):
        logger.info(self, '\n')
        logger.info(self, '******** PBC CC flags ********')
        gccsd.GCCSD.dump_flags(self)
        return self

    def init_amps(self, eris):
        time0 = time.clock(), time.time()
        nocc = self.get_nocc()
        nvir = self.get_nmo() - nocc
        nkpts = self.nkpts
        t1 = numpy.zeros((nkpts,nocc,nvir), dtype=numpy.complex128)
        t2 = numpy.zeros((nkpts,nkpts,nkpts,nocc,nocc,nvir,nvir), dtype=numpy.complex128)
        self.emp2 = 0
        foo = eris.fock[:,:nocc,:nocc].copy()
        fvv = eris.fock[:,nocc:,nocc:].copy()
        eris_oovv = eris.oovv.copy()
        eia = numpy.zeros((nocc,nvir))
        eijab = numpy.zeros((nocc,nocc,nvir,nvir))

        kconserv = kpts_helper.get_kconserv(self._scf.cell,self.kpts)
        for ki, kj, ka in kpts_helper.loop_kkk(nkpts):
            kb = kconserv[ki,ka,kj]
            for i in range(nocc):
                for a in range(nvir):
                    eia[i,a] = (foo[ki,i,i] - fvv[ka,a,a]).real
                    for j in range(nocc):
                        for b in range(nvir):
                            eijab[i,j,a,b] = ( foo[ki,i,i] + foo[kj,j,j]
                                             - fvv[ka,a,a] - fvv[kb,b,b]).real
                            t2[ki,kj,ka,i,j,a,b] = eris_oovv[ki,kj,ka,i,j,a,b]/eijab[i,j,a,b]

        t2 = numpy.conj(t2)
        self.emp2 = 0.25*numpy.einsum('pqrijab,pqrijab',t2,eris_oovv).real
        self.emp2 /= nkpts
        logger.info(self, 'Init t2, MP2 energy = %.15g', self.emp2.real)
        logger.timer(self, 'init mp2', *time0)
        #print("MP2 energy =", self.emp2)
        return self.emp2, t1, t2

    def ccsd(self, t1=None, t2=None, eris=None, **kwargs):
        if eris is None: eris = self.ao2mo(self.mo_coeff)
        self.converged, self.e_corr, self.t1, self.t2 = \
                kernel(self, eris, t1, t2, max_cycle=self.max_cycle,
                       tol=self.conv_tol,
                       tolnormt=self.conv_tol_normt,
                       max_memory=self.max_memory, verbose=self.verbose)
        if self.converged:
            logger.info(self, 'CCSD converged')
        else:
            logger.info(self, 'CCSD not converge')
        if self._scf.e_tot == 0:
            logger.info(self, 'E_corr = %.16g', self.e_corr)
        else:
            logger.info(self, 'E(CCSD) = %.16g  E_corr = %.16g',
                        self.e_corr+self._scf.e_tot, self.e_corr)
        return self.e_corr, self.t1, self.t2

    def ao2mo(self, mo_coeff=None):
        nkpts = self.nkpts
        nmo = self.nmo
        mem_incore = nkpts**3*nmo**4 * 8/1e6
        mem_now = lib.current_memory()[0]

        if (mem_incore+mem_now < self.max_memory) or self.mol.incore_anyway:
            return _make_eris_incore(self, mo_coeff)
        else:
            raise NotImplementedError

    def update_amps(self, t1, t2, eris, max_memory=2000):
        return update_amps(self, t1, t2, eris, max_memory)

    def amplitudes_to_vector(self, t1, t2):
        return numpy.hstack((t1.ravel(), t2.ravel()))

    def vector_to_amplitudes(self, vec, nmo=None, nocc=None):
        if nocc is None: nocc = self.nocc
        if nmo is None: nmo = self.nmo
        nvir = nmo - nocc
        nkpts = self.nkpts
        nov = nkpts*nocc*nvir
        t1 = vec[:nov].reshape(nkpts,nocc,nvir)
        t2 = vec[nov:].reshape(nkpts,nkpts,nkpts,nocc,nocc,nvir,nvir)
        return t1, t2

CCSD = GCCSD


def _make_eris_incore(cc, mo_coeff=None):
    log = logger.Logger(cc.stdout, cc.verbose)
    cput0 = (time.clock(), time.time())
    eris = gccsd._PhysicistsERIs()
    kpts = cc.kpts
    nkpts = cc.nkpts

    if mo_coeff is None:
        # If mo_coeff is not canonical orbital
        # TODO does this work for k-points? changed to conjugate.
        raise NotImplementedError
        mo_coeff = cc.mo_coeff
    moidx = get_frozen_mask(cc)
    eris.mo_coeff = []
    eris.orbspin = []
    for k in range(nkpts):
        mo = mo_coeff[k][:,moidx[k]]
        if hasattr(mo_coeff[k], 'orbspin'):
            orbspin = mo_coeff[k].orbspin[moidx[k]]
            mo = lib.tag_array(mo, orbspin=orbspin)
            eris.orbspin.append(orbspin)
        else:
            assert(numpy.count_nonzero(moidx[k]) % 2 == 0) # works for restricted CCSD only
            orbspin = numpy.zeros(mo.shape[1], dtype=int)
            orbspin[1::2] = 1
            mo = lib.tag_array(mo, orbspin=orbspin)
            eris.orbspin.append(orbspin)
        eris.mo_coeff.append(mo)

    dm = cc._scf.make_rdm1(cc.mo_coeff, cc.mo_occ)
    fockao = cc._scf.get_hcore() + cc._scf.get_veff(cc._scf.cell, dm)
    eris.fock = numpy.asarray([reduce(numpy.dot, (mo.T.conj(), fockao[k], mo))
                               for k, mo in enumerate(eris.mo_coeff)])

    nao, nmo = eris.mo_coeff[0].shape
    nocc = cc.get_nocc()
    nvir = nmo - nocc
    eris.nocc = nocc

    kconserv = kpts_helper.get_kconserv(cc._scf.cell,cc.kpts)
    so_coeff = [mo[:nao//2] + mo[nao//2:] for mo in eris.mo_coeff]

    eri = numpy.empty((nkpts,nkpts,nkpts,nmo,nmo,nmo,nmo), dtype=numpy.complex128)
    fao2mo = cc._scf.with_df.ao2mo
    for kp, kq, kr in kpts_helper.loop_kkk(nkpts):
        ks = kconserv[kp,kq,kr]
        eri_kpt = fao2mo((so_coeff[kp],so_coeff[kq],so_coeff[kr],so_coeff[ks]),
                         (kpts[kp],kpts[kq],kpts[kr],kpts[ks]), compact=False)
        eri_kpt[(eris.orbspin[kp][:,None] != eris.orbspin[kq]).ravel()] = 0
        eri_kpt[:,(eris.orbspin[kr][:,None] != eris.orbspin[ks]).ravel()] = 0
        eri_kpt = eri_kpt.reshape(nmo,nmo,nmo,nmo)
        eri[kp,kq,kr] = eri_kpt

    # Checking some things...
    if DEBUG:
        maxdiff = 0.0
        for kp, kq, kr in kpts_helper.loop_kkk(nkpts):
            ks = kconserv[kp,kq,kr]
            for p in range(nmo):
                for q in range(nmo):
                    for r in range(nmo):
                        for s in range(nmo):
                            pqrs = eri[kp,kq,kr,p,q,r,s]
                            rspq = eri[kr,ks,kp,r,s,p,q]
                            diff = numpy.linalg.norm(pqrs - rspq).real
                            if diff > 1e-5:
                                print("** Warning: ERI diff at ",)
                                print("kp,kq,kr,ks,p,q,r,s =", kp, kq, kr, ks, p, q, r, s)
                            maxdiff = max(maxdiff,diff)
        print("Max difference in (pq|rs) - (rs|pq) = %.15g" % maxdiff)
        #print("ERI =")
        #print(eri)

    # Antisymmetrizing (pq|rs)-(ps|rq), where the latter integral is equal to
    # (rq|ps); done since we aren't tracking the kpoint of orbital 's'
    eri1 = eri - eri.transpose(2,1,0,5,4,3,6)
    # Chemist -> physics notation
    eri1 = eri1.transpose(0,2,1,3,5,4,6)

    eris.dtype = eri1.dtype
    eris.oooo = eri1[:,:,:,:nocc,:nocc,:nocc,:nocc].copy() / nkpts
    eris.ooov = eri1[:,:,:,:nocc,:nocc,:nocc,nocc:].copy() / nkpts
    eris.ovoo = eri1[:,:,:,:nocc,nocc:,:nocc,:nocc].copy() / nkpts
    eris.oovv = eri1[:,:,:,:nocc,:nocc,nocc:,nocc:].copy() / nkpts
    eris.ovov = eri1[:,:,:,:nocc,nocc:,:nocc,nocc:].copy() / nkpts
    eris.ovvv = eri1[:,:,:,:nocc,nocc:,nocc:,nocc:].copy() / nkpts
    eris.vvvv = eri1[:,:,:,nocc:,nocc:,nocc:,nocc:].copy() / nkpts

    log.timer('CCSD integral transformation', *cput0)
    return eris


def check_antisymm_12( cc, kpts, integrals ):
    kconserv = kpts_helper.get_kconserv(cc._scf.cell,cc.kpts)
    nkpts = len(kpts)
    diff = 0.0
    for kp, kq, kr in kpts_helper.loop_kkk(nkpts):
        ks = kconserv[kp,kr,kq]
        for p in range(integrals.shape[3]):
            for q in range(integrals.shape[4]):
                for r in range(integrals.shape[5]):
                    for s in range(integrals.shape[6]):
                        pqrs = integrals[kp,kq,kr,p,q,r,s]
                        qprs = integrals[kq,kp,kr,q,p,r,s]
                        cdiff = numpy.linalg.norm(pqrs+qprs).real
                        print("AS diff = %.15g" % cdiff, pqrs, qprs, kp, kq, kr, ks, p, q, r, s)
                        diff = max(diff,cdiff)
    print("antisymmetrization : max diff = %.15g" % diff)

def check_antisymm_34( cc, kpts, integrals ):
    kconserv = kpts_helper.get_kconserv(cc._scf.cell,cc.kpts)
    nkpts = len(kpts)
    diff = 0.0
    for kp, kq, kr in kpts_helper.loop_kkk(nkpts):
        ks = kconserv[kp,kr,kq]
        for p in range(integrals.shape[3]):
            for q in range(integrals.shape[4]):
                for r in range(integrals.shape[5]):
                    for s in range(integrals.shape[6]):
                        pqrs = integrals[kp,kq,kr,p,q,r,s]
                        pqsr = integrals[kp,kq,ks,p,q,s,r]
                        cdiff = numpy.linalg.norm(pqrs+pqsr).real
                        print("AS diff = %.15g" % cdiff, pqrs, pqsr, kp, kq, kr, ks, p, q, r, s)
                        diff = max(diff,cdiff)
    print("antisymmetrization : max diff = %.15g" % diff)

