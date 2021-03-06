from __future__ import print_function, division
import os,unittest,numpy as np

class KnowValues(unittest.TestCase):

  def test_rsh_vec(self):
    """ Compute real spherical harmonics via a vectorized algorithm """
    from pyscf.nao.m_rsphar_libnao import rsphar_vec as rsphar_vec_libnao
    from pyscf.nao.m_rsphar_libnao import rsphar_exp_vec as rsphar_exp_vec_libnao
    from pyscf.nao.m_rsphar_vec import rsphar_vec as rsphar_vec_python
    from timeit import default_timer as timer
    
    ll = [0,1,2,3,4]
    crds = np.random.rand(20000, 3)
    for lmax in ll:
      t1 = timer()
      rsh1 = rsphar_exp_vec_libnao(crds.T, lmax)
      t2 = timer(); tpython = (t2-t1); t1 = timer()
      
      rsh2 = rsphar_vec_libnao(crds, lmax)
      t2 = timer(); tlibnao = (t2-t1); t1 = timer()
      
      #print( abs(rsh1.T-rsh2).sum(), tpython, tlibnao)
#      print( rsh1[1,:])
#      print( rsh2[1,:])

if __name__ == "__main__": unittest.main()
