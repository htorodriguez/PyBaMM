#
# Test the simulation class
#
import pybamm
import tests.shared as shared

import unittest
import os


class TestSimulation(unittest.TestCase):
    """Test the simulation class."""

    def test_simulation_setup(self):
        G = pybamm.Scalar(1)
        model = pybamm.electrolyte.StefanMaxwellDiffusion(G)

        # test default setup
        sim = pybamm.Simulation(model)
        self.assertEqual(sim.parameter_values, model.default_parameter_values)
        self.assertEqual(sim.discretisation, model.default_discretisation)
        self.assertEqual(sim.solver, model.default_solver)
        self.assertEqual(str(sim), "unnamed")

        # test custom setup
        parameter_values = pybamm.ParameterValues(
            "input/parameters/lithium-ion/parameters/LCO.csv"
        )
        mesh = shared.TestDefaults1DMacro().mesh
        discretisation = pybamm.FiniteVolumeDiscretisation(mesh)
        solver = pybamm.ScipySolver(method="RK45")

        sim = pybamm.Simulation(
            model,
            parameter_values=parameter_values,
            discretisation=discretisation,
            solver=solver,
            name="test name",
        )
        self.assertEqual(sim.parameter_values, parameter_values)
        self.assertEqual(sim.discretisation, discretisation)
        self.assertEqual(sim.solver, solver)
        self.assertEqual(str(sim), "test name")

    def test_simulation_run(self):
        G = pybamm.Scalar(0.1)
        model = pybamm.electrolyte.StefanMaxwellDiffusion(G)

        sim = pybamm.Simulation(model)
        sim.run()


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    unittest.main()
