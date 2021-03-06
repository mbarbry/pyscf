from __future__ import print_function, division
import os,unittest,numpy as np

try:
  from ase import Atoms
  from gpaw import GPAW
  skip_test = False
  fname = os.path.dirname(os.path.abspath(__file__))+'/h2o.gpw'

  if os.path.isfile(fname):
    calc = GPAW(fname, txt=None) # read previous calculation if the file exists
  else:
    from gpaw import PoissonSolver
    atoms = Atoms('H2O', positions=[[0.0,-0.757,0.587], [0.0,+0.757,0.587], [0.0,0.0,0.0]])
    atoms.center(vacuum=3.5)
    convergence = {'density': 1e-7}     # Increase accuracy of density for ground state
    poissonsolver = PoissonSolver(eps=1e-14, remove_moment=1 + 3)     # Increase accuracy of Poisson Solver and apply multipole corrections up to l=1
    calc = GPAW(basis='dzp', xc='LDA', h=0.3, nbands=23, convergence=convergence, poissonsolver=poissonsolver, mode='lcao', txt=None)     # nbands must be equal to norbs (in this case 23)
    atoms.set_calculator(calc)
    atoms.get_potential_energy()    # Do SCF the ground state
    calc.write(fname, mode='all') # write DFT output

except:
  skip_test = True

class KnowValues(unittest.TestCase):

  def test_nao_after_gpaw(self):
    """ Do GPAW LCAO calculation, then init system_vars_c with it """
    if skip_test: return

    #print(dir(calc.atoms))
    #print(dir(calc))
    #print(dir(calc.hamiltonian))
#    for aname in dir(calc.hamiltonian):
#      print(aname, getattr(calc.hamiltonian, aname))
    #print(calc.setups.id_a) # this is atom->specie !
    #print(dir(calc.setups))
    #print(calc.setups.nao)
    #print(dir(calc.setups.setups[(1, 'paw', u'dzp')])) 
#    O = calc.setups.setups[(8, 'paw', u'dzp')]
#    for aname in dir(O):
#      print(aname, getattr(O, aname))

if __name__ == "__main__": unittest.main()
