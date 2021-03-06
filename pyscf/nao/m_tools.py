"""
    modules containing tools and utility functions
"""

from __future__ import division
import numpy as np

def find_nearrest_index(arr, val):
    """
        return the index of an array which is the
        closest from the entered value

        Input Parameters:
        -----------------
            arr (1D numpy arr)
            val: value to find in the array

        Output Parameters:
        ------------------
            idx: index of arr corresponding to the closest
                from value
    """
    idx = (np.abs(arr-val)).argmin()
    return idx

def is_power2(n):
    """
        Check if n is a power of 2
    """
    assert isinstance(n, int)
    return ((n & (n-1)) == 0) and n != 0
