#
# Tests comparing model outputs for standard variables
#
import pybamm
import numpy as np


class StandardOutputComparison(object):
    "Calls all the tests comparing standard output variables."

    def __init__(self, models, discs, solutions):
        # Process variables
        for model in models:
            disc = discs[model]
            solution = solutions[model]
            model.variables = pybamm.post_process_variables(
                model.variables, solution.t, solution.y, disc.mesh
            )

        self.models = models
        self.discs = discs
        self.solutions = solutions

        if isinstance(self.models[0], pybamm.lithium_ion.BaseModel):
            self.chemistry = "Lithium-ion"
        elif isinstance(self.models[0], pybamm.lead_acid.BaseModel):
            self.chemistry = "Lead acid"

        self.t = self.get_output_times()
        self.mesh = self.get_mesh()

    def get_output_times(self):
        # Get max time allowed from the simulation, i.e. the smallest end time common
        # to all the solutions
        max_t = min([solution.t[-1] for solution in self.solutions.values()])

        # Assign common time
        solution0 = self.solutions[self.models[0]]
        max_index = np.where(solution0.t == max_t)[0][0]
        t_common = solution0.t[:max_index]

        # Check times
        for model in self.models:
            np.testing.assert_array_equal(t_common, self.solutions[model].t[:max_index])

        return t_common

    def get_mesh(self):
        disc0 = self.discs[self.models[0]]

        # Check all nodes and edges are the same
        for model in self.models:
            disc = self.discs[model]
            for domain in disc0.mesh:
                submesh0 = disc0.mesh[domain]
                submesh = disc.mesh[domain]
                np.testing.assert_array_equal(submesh0[0].nodes, submesh[0].nodes)
                np.testing.assert_array_equal(submesh0[0].edges, submesh[0].edges)
        return disc0.mesh

    def run_test_class(self, ClassName, skip_first_timestep=False):
        "Run all tests from a class 'ClassName'"
        if skip_first_timestep:
            t = self.t[1:]
        else:
            t = self.t
        tests = ClassName(self.models, t, self.mesh, self.solutions)
        tests.test_all()

    def test_averages(self, skip_first_timestep=False):
        self.run_test_class(AveragesComparison, skip_first_timestep)

    def test_all(self, skip_first_timestep=False):
        self.test_averages(skip_first_timestep)
        self.run_test_class(VariablesComparison, skip_first_timestep)

        if self.chemistry == "Lithium-ion":
            self.run_test_class(ParticleConcentrationComparison)
        elif self.chemistry == "Lead-acid":
            self.run_test_class(PorosityComparison)


class BaseOutputComparison(object):
    def __init__(self, models, time, mesh, solutions):
        self.models = models
        self.t = time
        self.mesh = mesh
        self.solutions = solutions

    def compare(self, var, tol=1e-2):
        "Compare variables from different models"
        # Get variable for each model
        model_variables = [model.variables[var] for model in self.models]
        var0 = model_variables[0]

        if var0.domain == []:
            x = None
        else:
            x = self.mesh.combine_submeshes(*var0.domain)[0].nodes

        # Calculate tolerance based on the value of var0
        maxvar0 = np.max(abs(var0(self.t, x)))
        if maxvar0 < 1e-14:
            decimal = -int(np.log10(tol))
        else:
            decimal = -int(np.log10(tol * maxvar0))
        # Check outputs are close to each other
        for model_var in model_variables[1:]:
            np.testing.assert_equal(var0.dimensions, model_var.dimensions)
            np.testing.assert_array_almost_equal(
                model_var(self.t, x), var0(self.t, x), decimal
            )


class AveragesComparison(BaseOutputComparison):
    "Compare variables whose average value should be the same across all models"

    def __init__(self, models, time, mesh, solutions):
        super().__init__(models, time, mesh, solutions)

    def test_all(self):
        # Potentials
        self.compare("X-averaged open circuit voltage")
        # Currents
        self.compare("X-averaged negative electrode interfacial current density")
        self.compare("X-averaged positive electrode interfacial current density")
        # Concentration
        self.compare("X-averaged electrolyte concentration")
        # Porosity
        self.compare("X-averaged negative electrode porosity")
        self.compare("X-averaged separator porosity")
        self.compare("X-averaged positive electrode porosity")


class VariablesComparison(BaseOutputComparison):
    "Compare variables across models"

    def __init__(self, models, time, mesh, solutions):
        super().__init__(models, time, mesh, solutions)

    def test_all(self):
        # Concentrations
        self.compare("Electrolyte concentration")
        # self.compare("Reduced cation flux")
        # Potentials
        # Some of these are 'average' but aren't expected to be the same across all
        # models
        self.compare("X-averaged reaction overpotential")
        self.compare("X-averaged negative electrode open circuit potential")
        self.compare("X-averaged positive electrode open circuit potential")
        self.compare("Terminal voltage")
        self.compare("X-averaged electrolyte overpotential")
        self.compare("X-averaged solid phase ohmic losses")
        self.compare("Negative electrode reaction overpotential")
        self.compare("Positive electrode reaction overpotential")
        self.compare("Negative electrode potential")
        self.compare("Positive electrode potential")
        self.compare("Electrolyte potential")
        # Currents
        self.compare("Exchange current density")
        self.compare("Negative electrode current density")
        self.compare("Positive electrode current density")


class ParticleConcentrationComparison(BaseOutputComparison):
    def __init__(self, models, time, mesh, solutions):
        super().__init__(models, time, mesh, solutions)

    def test_all(self):
        self.compare("Negative particle concentration")
        self.compare("Positive particle concentration")
        self.compare("Negative particle flux")
        self.compare("Positive particle flux")


class PorosityComparison(BaseOutputComparison):
    def __init__(self, models, time, mesh, solutions):
        super().__init__(models, time, mesh, solutions)

    def test_all(self):
        self.compare("Porosity")
