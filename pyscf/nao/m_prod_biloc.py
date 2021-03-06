from __future__ import print_function, division
import collections

#
# Hopefully a dict should be more memory saving than a class??
#
def set_prod_biloc(atoms, vrtx, cc2a, cc2s, cc):
    assert vrtx.shape[0]==cc.shape[0]
    assert cc2s[-1]==cc.shape[1]

    return {"atoms": atoms, "vrtx": vrtx, "cc2a": cc2a,
            "cc2s": cc2s, "cc": cc}

#
#
#
class prod_biloc_c():
  '''
  Holder of bilocal product vertices and conversion coefficients.
  Args:
    atoms : atom pair (atom indices)
    vrtx : dominant product vertex coefficients: product,orb1,orb0
    cc2a : contributing center -> atom index
    cc2s : contributing center -> start of the local product's counting
    cc   : conversion coefficients: product, atom-centered product
  Returns:
    structure with these fields
  '''
  def __init__(self, atoms, vrtx, cc2a, cc2s, cc):
    assert vrtx.shape[0]==cc.shape[0]
    assert cc2s[-1]==cc.shape[1]

    self.atoms = atoms
    self.vrtx = vrtx
    self.cc2a = cc2a
    self.cc2s = cc2s
    self.cc   = cc
    return  
