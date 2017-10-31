from __future__ import division
import numpy as np
from scipy.sparse import csr_matrix, coo_matrix
from scipy.linalg import blas
from pyscf.nao.m_sparsetools import csr_matvec, csc_matvec, csc_matvecs

try:
    import numba
    from pyscf.nao.m_iter_div_eigenenergy_numba import div_eigenenergy_numba
    use_numba = True
except:
    use_numba = False

def chi0_mv(self, v, comega=1j*0.0):
    """
        Apply the non-interacting response function to a vector
        Input Parameters:
        -----------------
            self : tddft_iter or tddft_tem class
            v: vector describing the pertiurbation ??
            comega: complex frequency
    """

    if v.dtype == self.dtypeComplex:
        vext = np.zeros((v.shape[0], 2), dtype = self.dtype, order="F")
        vext[:, 0] = v.real
        vext[:, 1] = v.imag

        # real part
        vdp = csr_matvec(self.cc_da, vext[:, 0])
        sab = (vdp*self.v_dab).reshape([self.norbs,self.norbs])

        nb2v = self.gemm(1.0, self.xocc, sab)
        nm2v_re = self.gemm(1.0, nb2v, self.xvrt.T)

        # imaginary part
        vdp = csr_matvec(self.cc_da, vext[:, 1])
        sab = (vdp*self.v_dab).reshape([self.norbs, self.norbs])

        nb2v = self.gemm(1.0, self.xocc, sab)
        nm2v_im = self.gemm(1.0, nb2v, self.xvrt.T)
    else:
        vext = np.zeros((v.shape[0], 2), dtype = self.dtype, order="F")
        vext[:, 0] = v.real

        vdp = csr_matvec(self.cc_da, vext[:, 0])
        sab = (vdp*self.v_dab).reshape([self.norbs, self.norbs])

        nb2v = self.gemm(1.0, self.xocc, sab)
        nm2v_re = self.gemm(1.0, nb2v, self.xvrt.T)

        nm2v_im = np.zeros(nm2v_re.shape, dtype = self.dtype)

    if use_numba:
        div_eigenenergy_numba(self.ksn2e[0, 0, :], self.ksn2f[0, 0, :], self.nfermi, 
                self.vstart, comega, nm2v_re, nm2v_im, self.norbs)
    else:
        for n,[en,fn] in enumerate(zip(self.ksn2e[0:self.nfermi], self.ksn2f[0, 0, 0:self.nfermi])):
            for j,[em,fm] in enumerate(zip(self.ksn2e[0, 0, n+1:],self.ksn2f[0, 0, n+1:])):
                m = j+n+1-self.vstart
                nm2v = nm2v_re[n, m] + 1.0j*nm2v_im[n, m]
                nm2v = nm2v * (fn-fm) *\
                        ( 1.0 / (comega - (em - en)) - 1.0 / (comega + (em - en)) )
                nm2v_re[n, m] = nm2v.real
                nm2v_im[n, m] = nm2v.imag

    # real part
    nb2v = self.gemm(1.0, nm2v_re, self.xvrt)
    ab2v = self.gemm(1.0, self.xocc.T, nb2v).reshape(self.norbs*self.norbs)
    vdp = csr_matvec(self.v_dab, ab2v)
    
    chi0_re = vdp*self.cc_da

    # imag part
    nb2v = self.gemm(1.0, nm2v_im, self.xvrt)
    ab2v = self.gemm(1.0, self.xocc.T, nb2v).reshape(self.norbs*self.norbs)
    vdp = csr_matvec(self.v_dab, ab2v)
    
    chi0_im = vdp*self.cc_da

    return chi0_re + 1.0j*chi0_im

def chi0_mv_gpu(self, v, comega=1j*0.0):
#        tddft_iter_gpu, v, cc_da, v_dab, no,
#        comega=1j*0.0, dtype=np.float32, cdtype=np.complex64):
    """
        Apply the non-interacting response function to a vector using gpu for
        matrix-matrix multiplication
    """

    if self.dtype != np.float32:
        print(self.dtype)
        raise ValueError("GPU version only with single precision")

    vext = np.zeros((v.shape[0], 2), dtype = self.dtype, order="F")
    vext[:, 0] = v.real
    vext[:, 1] = v.imag

    # real part
    vdp = csr_matvec(self.cc_da, vext[:, 0])
    sab = (vdp*self.v_dab).reshape([self.norbs, self.norbs])

    self.td_GPU.cpy_sab_to_device(sab, Async = 1)
    self.td_GPU.calc_nb2v_from_sab(reim=0)
    # nm2v_real
    self.td_GPU.calc_nm2v_real()


    # start imaginary part
    vdp = csr_matvec(self.cc_da, vext[:, 1])
    sab = (vdp*self.v_dab).reshape([self.norbs, self.norbs])
    self.td_GPU.cpy_sab_to_device(sab, Async = 2)


    self.td_GPU.calc_nb2v_from_sab(reim=1)
    # nm2v_imag
    self.td_GPU.calc_nm2v_imag()

    self.td_GPU.div_eigenenergy_gpu(comega)

    # real part
    self.td_GPU.calc_nb2v_from_nm2v_real()
    self.td_GPU.calc_sab(reim=0)
    self.td_GPU.cpy_sab_to_host(sab, Async = 1)

    # start calc_ imag to overlap with cpu calculations
    self.td_GPU.calc_nb2v_from_nm2v_imag()

    vdp = csr_matvec(self.v_dab, sab)
    
    self.td_GPU.calc_sab(reim=1)

    # finish real part 
    chi0_re = vdp*self.cc_da

    # imag part
    self.td_GPU.cpy_sab_to_host(sab)

    vdp = csr_matvec(self.v_dab, sab)
    chi0_im = vdp*self.cc_da

    return chi0_re + 1.0j*chi0_im
