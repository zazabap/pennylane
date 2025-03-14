# Copyright 2018-2020 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Pytest configuration file for PennyLane test suite.
"""
# pylint: disable=unused-import
import os
import pathlib
import sys
from warnings import filterwarnings, warn

import numpy as np
import pytest

import pennylane as qml
from pennylane.devices import DefaultGaussian
from pennylane.operation import disable_new_opmath_cm, enable_new_opmath_cm

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

# defaults
TOL = 1e-3
TF_TOL = 2e-2
TOL_STOCHASTIC = 0.05


# pylint: disable=too-few-public-methods
class DummyDevice(DefaultGaussian):
    """Dummy device to allow Kerr operations"""

    _operation_map = DefaultGaussian._operation_map.copy()
    _operation_map["Kerr"] = lambda *x, **y: np.identity(2)


@pytest.fixture(scope="session")
def tol():
    """Numerical tolerance for equality tests."""
    return float(os.environ.get("TOL", TOL))


@pytest.fixture(scope="session")
def tol_stochastic():
    """Numerical tolerance for equality tests of stochastic values."""
    return TOL_STOCHASTIC


@pytest.fixture(scope="session")
def tf_tol():
    """Numerical tolerance for equality tests."""
    return float(os.environ.get("TF_TOL", TF_TOL))


@pytest.fixture(scope="session", params=[1, 2])
def n_layers(request):
    """Number of layers."""
    return request.param


@pytest.fixture(scope="session", params=[2, 3], name="n_subsystems")
def n_subsystems_fixture(request):
    """Number of qubits or qumodes."""
    return request.param


@pytest.fixture(scope="session")
def qubit_device(n_subsystems):
    return qml.device("default.qubit", wires=n_subsystems)


# The following 3 fixtures are for default.qutrit devices to be used
# for testing with various real and complex dtypes.


@pytest.fixture(scope="function", params=[(np.float32, np.complex64), (np.float64, np.complex128)])
def qutrit_device_1_wire(request):
    return qml.device("default.qutrit", wires=1, r_dtype=request.param[0], c_dtype=request.param[1])


@pytest.fixture(scope="function", params=[(np.float32, np.complex64), (np.float64, np.complex128)])
def qutrit_device_2_wires(request):
    return qml.device("default.qutrit", wires=2, r_dtype=request.param[0], c_dtype=request.param[1])


@pytest.fixture(scope="function", params=[(np.float32, np.complex64), (np.float64, np.complex128)])
def qutrit_device_3_wires(request):
    return qml.device("default.qutrit", wires=3, r_dtype=request.param[0], c_dtype=request.param[1])


#######################################################################


@pytest.fixture(scope="function")
def mock_device(monkeypatch):
    """A mock instance of the abstract Device class"""

    with monkeypatch.context() as m:
        dev = qml.devices.LegacyDevice
        m.setattr(dev, "__abstractmethods__", frozenset())
        m.setattr(dev, "short_name", "mock_device")
        m.setattr(dev, "capabilities", lambda cls: {"model": "qubit"})
        m.setattr(dev, "operations", {"RX", "RY", "RZ", "CNOT", "SWAP"})
        yield qml.devices.LegacyDevice(wires=2)  # pylint:disable=abstract-class-instantiated


# pylint: disable=protected-access
@pytest.fixture
def tear_down_hermitian():
    yield None
    qml.Hermitian._eigs = {}


# pylint: disable=protected-access
@pytest.fixture
def tear_down_thermitian():
    yield None
    qml.THermitian._eigs = {}


#######################################################################
# Fixtures for testing under new and old opmath


def pytest_addoption(parser):
    parser.addoption(
        "--disable-opmath", action="store", default="False", help="Whether to disable new_opmath"
    )


# pylint: disable=eval-used
@pytest.fixture(scope="session", autouse=True)
def disable_opmath_if_requested(request):
    disable_opmath = request.config.getoption("--disable-opmath")
    # value from yaml file is a string, convert to boolean
    if eval(disable_opmath):
        warn(
            "Disabling the new Operator arithmetic system for legacy support. "
            "If you need help troubleshooting your code, please visit "
            "https://docs.pennylane.ai/en/stable/news/new_opmath.html",
            UserWarning,
        )
        qml.operation.disable_new_opmath(warn=False)

        # Suppressing warnings so that Hamiltonians and Tensors constructed outside tests
        # don't raise deprecation warnings
        filterwarnings("ignore", "qml.ops.Hamiltonian", qml.PennyLaneDeprecationWarning)
        filterwarnings("ignore", "qml.operation.Tensor", qml.PennyLaneDeprecationWarning)
        filterwarnings("ignore", "qml.pauli.simplify", qml.PennyLaneDeprecationWarning)
        filterwarnings("ignore", "PauliSentence.hamiltonian", qml.PennyLaneDeprecationWarning)
        filterwarnings("ignore", "PauliWord.hamiltonian", qml.PennyLaneDeprecationWarning)


@pytest.fixture(params=[disable_new_opmath_cm, enable_new_opmath_cm], scope="function")
def use_legacy_and_new_opmath(request):
    with request.param(warn=False) as cm:
        yield cm


@pytest.fixture
def new_opmath_only():
    if not qml.operation.active_new_opmath():
        pytest.skip("This feature only works with new opmath enabled")


@pytest.fixture
def legacy_opmath_only():
    if qml.operation.active_new_opmath():
        pytest.skip("This test exclusively tests legacy opmath")


#######################################################################


@pytest.fixture(autouse=True)
def restore_global_seed():
    original_state = np.random.get_state()
    yield
    np.random.set_state(original_state)


@pytest.fixture
def seed(request):
    """An integer random number generator seed

    This fixture overrides the ``seed`` fixture provided by pytest-rng, adding the flexibility
    of locally getting a new seed for a test case by applying the ``local_salt`` marker. This is
    useful when the seed from pytest-rng happens to be a bad seed that causes your test to fail.

    .. code_block:: python

        @pytest.mark.local_salt(42)
        def test_something(seed):
            ...

    The value passed to ``local_salt`` needs to be an integer.

    """

    fixture_manager = request._fixturemanager  # pylint:disable=protected-access
    fixture_defs = fixture_manager.getfixturedefs("seed", request.node)
    original_fixture_def = fixture_defs[0]  # the original seed fixture provided by pytest-rng
    original_seed = original_fixture_def.func(request)
    marker = request.node.get_closest_marker("local_salt")
    if marker and marker.args:
        return original_seed + marker.args[0]
    return original_seed


#######################################################################

try:
    import tensorflow as tf
except (ImportError, ModuleNotFoundError) as e:
    tf_available = False
else:
    tf_available = True

try:
    import torch
    from torch.autograd import Variable

    torch_available = True
except ImportError as e:
    torch_available = False

try:
    import jax
    import jax.numpy as jnp

    jax_available = True
except ImportError as e:
    jax_available = False


# pylint: disable=unused-argument
def pytest_generate_tests(metafunc):
    if jax_available:
        jax.config.update("jax_enable_x64", True)


def pytest_collection_modifyitems(items, config):
    rootdir = pathlib.Path(config.rootdir)
    for item in items:
        rel_path = pathlib.Path(item.fspath).relative_to(rootdir)
        if "qchem" in rel_path.parts:
            mark = getattr(pytest.mark, "qchem")
            item.add_marker(mark)
        if "finite_diff" in rel_path.parts:
            mark = getattr(pytest.mark, "finite-diff")
            item.add_marker(mark)
        if "parameter_shift" in rel_path.parts:
            mark = getattr(pytest.mark, "param-shift")
            item.add_marker(mark)
        if "data" in rel_path.parts:
            mark = getattr(pytest.mark, "data")
            item.add_marker(mark)

    # Tests that do not have a specific suite marker are marked `core`
    for item in items:
        markers = {mark.name for mark in item.iter_markers()}
        if (
            not any(
                elem
                in [
                    "autograd",
                    "data",
                    "torch",
                    "tf",
                    "jax",
                    "qchem",
                    "qcut",
                    "all_interfaces",
                    "finite-diff",
                    "param-shift",
                    "external",
                ]
                for elem in markers
            )
            or not markers
        ):
            item.add_marker(pytest.mark.core)


def pytest_runtest_setup(item):
    """Automatically skip tests if interfaces are not installed"""
    # Autograd is assumed to be installed
    interfaces = {"tf", "torch", "jax"}
    available_interfaces = {
        "tf": tf_available,
        "torch": torch_available,
        "jax": jax_available,
    }

    allowed_interfaces = [
        allowed_interface
        for allowed_interface in interfaces
        if available_interfaces[allowed_interface] is True
    ]

    # load the marker specifying what the interface is
    all_interfaces = {"tf", "torch", "jax", "all_interfaces"}
    marks = {mark.name for mark in item.iter_markers() if mark.name in all_interfaces}

    for b in marks:
        if b == "all_interfaces":
            required_interfaces = {"tf", "torch", "jax"}
            for interface in required_interfaces:
                if interface not in allowed_interfaces:
                    pytest.skip(
                        f"\nTest {item.nodeid} only runs with {allowed_interfaces} interfaces(s) but {b} interface provided",
                    )
        else:
            if b not in allowed_interfaces:
                pytest.skip(
                    f"\nTest {item.nodeid} only runs with {allowed_interfaces} interfaces(s) but {b} interface provided",
                )
