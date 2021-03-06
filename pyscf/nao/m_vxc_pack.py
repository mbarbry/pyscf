from __future__ import print_function, division
from numpy import array, int64, zeros, float64
try:
    import numba as nb
    from pyscf.nao.m_numba_utils import fill_triu_v2
    use_numba = True
except:
    use_numba = False


#
#
#
def vxc_pack(self, **kw):
  """
    Computes the exchange-correlation matrix elements packed version (upper triangular)
    Args:
      sv : (System Variables), this must have arrays of coordinates and species, etc
    Returns:
      vxc,exc
  """
  from pyscf.nao.m_xc_scalar_ni import xc_scalar_ni
  from pyscf.nao.m_ao_matelem import ao_matelem_c

  #sv, dm, xc_code, deriv, kernel=None, ao_log=None, dtype=float64, **kvargs
  sv = self
  dm = kw['dm'] if 'dm' in kw else self.make_rdm1()
  kernel = kw['kernel'] if 'kernel' in kw else None
  ao_log = kw['ao_log'] if 'ao_log' in kw else self.ao_log
  (xc_code,iskw) = (kw['xc_code'],True) if 'xc_code' in kw else (self.xc_code,False)
  dtype = kw['dtype'] if 'dtype' in kw else float64

  aome = ao_matelem_c(ao_log.rr, ao_log.pp, sv, dm)
  me = aome.init_one_set(ao_log)
  atom2s = zeros((sv.natm+1), dtype=int64)
  for atom,sp in enumerate(sv.atom2sp): atom2s[atom+1]=atom2s[atom]+me.ao1.sp2norbs[sp]
  sp2rcut = array([max(mu2rcut) for mu2rcut in me.ao1.sp_mu2rcut])
  norbs = atom2s[-1]

  #ind = triu_indices(norbs)
  if kernel is None: kernel = zeros(norbs*(norbs+1)//2, dtype=dtype)

  if kernel.size != int(norbs*(norbs+1)//2):
    print('kernel.size        ', kernel.size)
    print('norbs*(norbs+1)//2 ', int(norbs*(norbs+1)//2))
    raise ValueError("wrong dimension for kernel")
    

  for atom1,[sp1,rv1,s1,f1] in enumerate(zip(sv.atom2sp,sv.atom2coord,atom2s,atom2s[1:])):
    for atom2,[sp2,rv2,s2,f2] in enumerate(zip(sv.atom2sp,sv.atom2coord,atom2s,atom2s[1:])):
      if atom2>atom1: continue
      if (sp2rcut[sp1]+sp2rcut[sp2])**2<=sum((rv1-rv2)**2) : continue
      
      xc = xc_scalar_ni(me,sp1,rv1,sp2,rv2,**kw) if iskw else xc_scalar_ni(me,sp1,rv1,sp2,rv2,xc_code=xc_code,**kw)
      
      if use_numba:
          fill_triu_v2(xc, kernel, s1, f1, s2, f2, norbs, add=True)
      else:
          for i1 in range(s1,f1):
            for i2 in range(s2, min(i1+1, f2)):
                ind = 0
                if i2 > 0:
                    for beta in range(1, i2+1):
                        ind += norbs -beta
                ind += i1
                kernel[ind] += xc[i1-s1,i2-s2] 
  return kernel
