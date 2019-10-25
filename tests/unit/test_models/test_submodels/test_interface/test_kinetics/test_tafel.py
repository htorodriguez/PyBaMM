#
# Test base butler volmer submodel
#

import pybamm
import unittest


class TestTafel(unittest.TestCase):
    def test_forward_tafel(self):
        submodel = pybamm.interface.kinetics.ForwardTafel(None, None)
        j = submodel._get_kinetics(pybamm.Scalar(1), pybamm.Scalar(1), pybamm.Scalar(1))
        self.assertIsInstance(j, pybamm.Symbol)

    def test_backward_tafel(self):
        submodel = pybamm.interface.kinetics.BackwardTafel(None, None)
        j = submodel._get_kinetics(pybamm.Scalar(1), pybamm.Scalar(1), pybamm.Scalar(1))
        self.assertIsInstance(j, pybamm.Symbol)


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    pybamm.settings.debug_mode = True
    unittest.main()
