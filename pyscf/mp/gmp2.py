'''
GMP2 in spin-orbital form
E(MP2) = 1/4 <ij||ab><ab||ij>/(ei+ej-ea-eb)
'''

import time
import numpy
from pyscf import lib
from pyscf import ao2mo
from pyscf.lib import logger
from pyscf.mp import mp2
from pyscf import scf

def kernel(mp, mo_energy=None, mo_coeff=None, eris=None, with_t2=True,
           verbose=logger.NOTE):
    if mo_energy is None or mo_coeff is None:
        mo_coeff = None
        mo_energy = mp.mo_energy[mp.get_frozen_mask()]
    else:
        # For backward compatibility.  In pyscf-1.4 or earlier, mp.frozen is
        # not supported when mo_energy or mo_coeff is given.
        assert(mp.frozen is 0 or mp.frozen is None)

    if eris is None: eris = mp.ao2mo(mo_coeff)

    nocc = mp.nocc
    nvir = mp.nmo - nocc
    moidx = mp.get_frozen_mask()
    eia = mo_energy[:nocc,None] - mo_energy[None,nocc:]

    if with_t2:
        t2 = numpy.empty((nocc,nocc,nvir,nvir))
    else:
        t2 = None

    emp2 = 0
    for i in range(nocc):
        gi = numpy.asarray(eris.oovv[i]).reshape(nocc,nvir,nvir)
        t2i = gi.conj()/lib.direct_sum('jb+a->jba', eia, eia[i])
        emp2 += numpy.einsum('jab,jab', t2i, gi) * .25
        if with_t2:
            t2[i] = t2i

    return emp2.real, t2

def make_rdm1(mp, t2=None):
    if t2 is None: t2 = mp.t2
    from pyscf.cc import gccsd_rdm
    doo, dvv = _gamma1_intermediates(mp, t2)
    nocc, nvir = t2.shape[1:3]
    dov = numpy.zeros((nocc,nvir))
    d1 = doo, dov, dov.T, dvv
    return gccsd_rdm._make_rdm1(mp, d1, with_frozen=True)

def _gamma1_intermediates(mp, t2):
    doo = lib.einsum('imef,jmef->ij', t2.conj(), t2) *-.5
    dvv = lib.einsum('mnea,mneb->ab', t2, t2.conj()) * .5
    return doo, dvv

# spin-orbital rdm2 in Chemist's notation
def make_rdm2(mp, t2=None):
    if t2 is None: t2 = mp.t2
    nmo = nmo0 = mp.nmo
    nocc = nocc0 = mp.nocc

    if not (mp.frozen is 0 or mp.frozen is None):
        nmo0 = mp.mo_occ.size
        nocc0 = numpy.count_nonzero(mp.mo_occ > 0)
        moidx = mp.get_frozen_mask()
        oidx = numpy.where(moidx & (mp.mo_occ > 0))[0]
        vidx = numpy.where(moidx & (mp.mo_occ ==0))[0]

        dm2 = numpy.zeros((nmo0,nmo0,nmo0,nmo0)) # Chemist notation
        dm2[oidx[:,None,None,None],vidx[:,None,None],oidx[:,None],vidx] = \
                (t2.transpose(0,2,1,3) - t2.transpose(0,3,1,2)) * .5
        dm2[nocc0:,:nocc0,nocc0:,:nocc0] = \
                dm2[:nocc0,nocc0:,:nocc0,nocc0:].transpose(1,0,3,2).conj()
    else:
        dm2 = numpy.zeros((nmo0,nmo0,nmo0,nmo0)) # Chemist notation
        dm2[:nocc,nocc:,:nocc,nocc:] = (t2.transpose(0,2,1,3) - t2.transpose(0,3,1,2)) * .5
        dm2[nocc:,:nocc,nocc:,:nocc] = dm2[:nocc,nocc:,:nocc,nocc:].transpose(1,0,3,2).conj()

    dm1 = make_rdm1(mp, t2)
    dm1[numpy.diag_indices(nocc0)] -= 1

    for i in range(nocc0):
        dm2[i,i,:,:] += dm1
        dm2[:,:,i,i] += dm1
        dm2[:,i,i,:] -= dm1
        dm2[i,:,:,i] -= dm1

    for i in range(nocc0):
        for j in range(nocc0):
            dm2[i,i,j,j] += 1
            dm2[i,j,j,i] -= 1

    return dm2


class GMP2(mp2.MP2):
    def __init__(self, mf, frozen=0, mo_coeff=None, mo_occ=None):
        assert(isinstance(mf, scf.ghf.GHF))
        mp2.MP2.__init__(self, mf, frozen, mo_coeff, mo_occ)

    @lib.with_doc(mp2.MP2.kernel.__doc__)
    def kernel(self, mo_energy=None, mo_coeff=None, eris=None, with_t2=True):
        return mp2.MP2.kernel(self, mo_energy, mo_coeff, eris, with_t2, kernel)

    def ao2mo(self, mo_coeff=None):
        if mo_coeff is None: mo_coeff = self.mo_coeff
        nmo = self.nmo
        nocc = self.nocc
        nvir = nmo - nocc
        mem_incore = nocc**2*nvir**2*3 * 8/1e6
        mem_now = lib.current_memory()[0]
        if (self._scf._eri is not None and
            (mem_incore+mem_now < self.max_memory) or self.mol.incore_anyway):
            return _make_eris_incore(self, mo_coeff, verbose=self.verbose)
        elif hasattr(self._scf, 'with_df'):
            raise NotImplementedError
        else:
            return _make_eris_outcore(self, mo_coeff, self.verbose)

    make_rdm1 = make_rdm1
    make_rdm2 = make_rdm2


class _PhysicistsERIs:
    def __init__(self, mp, mo_coeff=None):
        self.orbspin = None

        if mo_coeff is None:
            mo_coeff = mp.mo_coeff
        mo_idx = mp.get_frozen_mask()
        if hasattr(mo_coeff, 'orbspin'):
            self.orbspin = mo_coeff.orbspin[mo_idx]
            mo_coeff = lib.tag_array(mo_coeff[:,mo_idx], orbspin=self.orbspin)
            self.mo_coeff = mo_coeff
        else:
            orbspin = scf.ghf.guess_orbspin(mo_coeff)
            self.mo_coeff = mo_coeff = mo_coeff[:,mo_idx]
            if not numpy.any(orbspin == -1):
                self.orbspin = orbspin[mo_idx]
                self.mo_coeff = lib.tag_array(mo_coeff, orbspin=self.orbspin)

def _make_eris_incore(mp, mo_coeff=None, ao2mofn=None, verbose=None):
    eris = _PhysicistsERIs(mp, mo_coeff)

    nocc = mp.nocc
    nao, nmo = eris.mo_coeff.shape
    nvir = nmo - nocc
    orboa = eris.mo_coeff[:nao//2,:nocc]
    orbob = eris.mo_coeff[nao//2:,:nocc]
    orbva = eris.mo_coeff[:nao//2,nocc:]
    orbvb = eris.mo_coeff[nao//2:,nocc:]
    orbspin = eris.orbspin

    if not callable(ao2mofn):
        ao2mofn = lambda *args: ao2mo.kernel(mp._scf._eri, *args)

    if orbspin is None:
        eri  = ao2mofn((orboa,orbva,orboa,orbva)).reshape(nocc,nvir,nocc,nvir)
        eri += ao2mofn((orbob,orbvb,orbob,orbvb)).reshape(nocc,nvir,nocc,nvir)
        eri1 = ao2mofn((orboa,orbva,orbob,orbvb)).reshape(nocc,nvir,nocc,nvir)
        eri += eri1
        eri += eri1.transpose(2,3,0,1)
    else:
        co = orboa + orbob
        cv = orbva + orbvb
        eri = ao2mofn((co,cv,co,cv)).reshape(nocc,nvir,nocc,nvir)
        sym_forbid = (orbspin[:nocc,None] != orbspin[nocc:])
        eri[sym_forbid,:,:] = 0
        eri[:,:,sym_forbid] = 0

    eri = eri.reshape(nocc,nvir,nocc,nvir)
    eris.oovv = eri.transpose(0,2,1,3) - eri.transpose(0,2,3,1)
    return eris

def _make_eris_outcore(mp, mo_coeff=None, verbose=None):
    cput0 = (time.clock(), time.time())
    log = logger.Logger(mp.stdout, mp.verbose)
    eris = _PhysicistsERIs(mp, mo_coeff)

    nocc = mp.nocc
    nao, nmo = eris.mo_coeff.shape
    nvir = nmo - nocc
    assert(eris.mo_coeff.dtype == numpy.double)
    orboa = eris.mo_coeff[:nao//2,:nocc]
    orbob = eris.mo_coeff[nao//2:,:nocc]
    orbva = eris.mo_coeff[:nao//2,nocc:]
    orbvb = eris.mo_coeff[nao//2:,nocc:]
    orbspin = eris.orbspin

    feri = eris.feri = lib.H5TmpFile()
    eris.oovv = feri.create_dataset('oovv', (nocc,nocc,nvir,nvir), 'f8')

    if orbspin is None:
        max_memory = mp.max_memory-lib.current_memory()[0]
        blksize = min(nocc, max(2, int(max_memory*1e6/8/(nocc*nvir**2*2))))
        max_memory = max(2000, max_memory)

        fswap = lib.H5TmpFile()
        ao2mo.kernel(mp.mol, (orboa,orbva,orboa,orbva), fswap, 'aaaa',
                     max_memory=max_memory, verbose=log)
        ao2mo.kernel(mp.mol, (orboa,orbva,orbob,orbvb), fswap, 'aabb',
                     max_memory=max_memory, verbose=log)
        ao2mo.kernel(mp.mol, (orbob,orbvb,orboa,orbva), fswap, 'bbaa',
                     max_memory=max_memory, verbose=log)
        ao2mo.kernel(mp.mol, (orbob,orbvb,orbob,orbvb), fswap, 'bbbb',
                     max_memory=max_memory, verbose=log)

        for p0, p1 in lib.prange(0, nocc, blksize):
            tmp  = numpy.asarray(fswap['aaaa'][p0*nvir:p1*nvir])
            tmp += numpy.asarray(fswap['aabb'][p0*nvir:p1*nvir])
            tmp += numpy.asarray(fswap['bbaa'][p0*nvir:p1*nvir])
            tmp += numpy.asarray(fswap['bbbb'][p0*nvir:p1*nvir])
            tmp = tmp.reshape(p1-p0,nvir,nocc,nvir)
            eris.oovv[p0:p1] = tmp.transpose(0,2,1,3) - tmp.transpose(0,2,3,1)

    else:  # with orbspin
        orbo = orboa + orbob
        orbv = orbva + orbvb

        max_memory = mp.max_memory-lib.current_memory()[0]
        blksize = min(nocc, max(2, int(max_memory*1e6/8/(nocc*nvir**2*2))))
        max_memory = max(2000, max_memory)

        fswap = lib.H5TmpFile()
        ao2mo.kernel(mp.mol, (orbo,orbv,orbo,orbv), fswap,
                     max_memory=max_memory, verbose=log)
        sym_forbid = orbspin[:nocc,None] != orbspin[nocc:]

        for p0, p1 in lib.prange(0, nocc, blksize):
            tmp = numpy.asarray(fswap['eri_mo'][p0*nvir:p1*nvir])
            tmp = tmp.reshape(p1-p0,nvir,nocc,nvir)
            tmp[sym_forbid[p0:p1]] = 0
            tmp[:,:,sym_forbid] = 0
            eris.oovv[p0:p1] = tmp.transpose(0,2,1,3) - tmp.transpose(0,2,3,1)

    cput0 = log.timer_debug1('transforming oovv', *cput0)
    return eris


if __name__ == '__main__':
    from pyscf import scf
    from pyscf import gto
    mol = gto.Mole()
    mol.atom = [['O', (0.,   0., 0.)],
                ['O', (1.21, 0., 0.)]]
    mol.basis = 'cc-pvdz'
    mol.spin = 2
    mol.build()
    mf = scf.UHF(mol).run()
    mf = scf.addons.convert_to_ghf(mf)

    frozen = [0,1,2,3]
    pt = GMP2(mf, frozen=frozen)
    emp2, t2 = pt.kernel()
    print(emp2 - -0.345306881488508)

    pt.max_memory = 1
    emp2, t2 = pt.kernel()
    print(emp2 - -0.345306881488508)

    dm1 = pt.make_rdm1(t2)
    dm2 = pt.make_rdm2(t2)
    nao = mol.nao_nr()
    mo_a = mf.mo_coeff[:nao]
    mo_b = mf.mo_coeff[nao:]
    nmo = mo_a.shape[1]
    eri = ao2mo.kernel(mf._eri, mo_a+mo_b, compact=False).reshape([nmo]*4)
    orbspin = mf.mo_coeff.orbspin
    sym_forbid = (orbspin[:,None] != orbspin)
    eri[sym_forbid,:,:] = 0
    eri[:,:,sym_forbid] = 0
    hcore = scf.RHF(mol).get_hcore()
    h1 = reduce(numpy.dot, (mo_a.T.conj(), hcore, mo_a))
    h1+= reduce(numpy.dot, (mo_b.T.conj(), hcore, mo_b))
    e1 = numpy.einsum('ij,ji', h1, dm1)
    e1+= numpy.einsum('ijkl,jilk', eri, dm2) * .5
    e1+= mol.energy_nuc()
    print(e1 - pt.e_tot)
