#
# Spatial method for zero dimensional meshes
#
import pybamm
import numpy as np


class ZeroDimensionalMethod(pybamm.SpatialMethod):
    """
    A discretisation class for the zero dimensional mesh

    Parameters
    ----------
    mesh : :class: `pybamm.Mesh`
        Contains all the submeshes for discretisation

    **Extends** : :class:`pybamm.SpatialMethod`
    """

    def __init__(self, mesh=None):
        self._mesh = mesh

    def mass_matrix(self, symbol, boundary_conditions):
        """
        Calculates the mass matrix for a spatial method. Since the spatial method is
        zero dimensional, this is simply the number 1.
        """
        return pybamm.Matrix(np.ones((1, 1)))
