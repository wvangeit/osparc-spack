"""OSPARC-Simcore Spack Package"""

import multiprocessing
import os
import subprocess
import traceback

from spack.build_environment import MakeExecutable
from spack.package import (
    InstallError,
    Package,
    depends_on,
    install_tree,
    join_path,
    maintainers,
    mkdirp,
    run_after,
    run_before,
    tty,
    variant,
    version,
    which,
    working_dir,
)


class Osparc(Package):
    """o2S2PARC - Open Online Simulations for Stimulating Peripheral Activity
    to Relieve Conditions.

    A comprehensive, freely accessible, intuitive, and interactive online
    platform for simulating peripheral nerve system neuromodulation/stimulation
    and its impact on organ physiology in a precise and predictive manner.
    """

    homepage = "https://osparc.io"
    git = "https://github.com/ITISFoundation/osparc-simcore.git"
    url = (
        "https://github.com/ITISFoundation/osparc-simcore/"
        "archive/refs/tags/v1.0.0.tar.gz"
    )

    make = MakeExecutable(
        "make",
        jobs=1,
    )
    maintainers("wvangeit", "sanderegg", "pcrespov")

    # Versions
    version("master", branch="master", preferred=True)
    version("v1.0.0", tag="v1.0.0")

    # Variants following project structure
    variant(
        "prod",
        default=False,
        description="Build for production deployment",
    )
    variant(
        "devel",
        default=True,
        description="Build for development with hot-reload",
    )
    variant(
        "frontend",
        default=True,
        description="Build frontend static-webserver",
    )
    variant(
        "tests",
        default=False,
        description="Install test dependencies and enable testing",
    )
    variant(
        "ops",
        default=True,
        description="Include ops stack (monitoring, portainer, etc.)",
    )
    variant(
        "vendors",
        default=True,
        description="Include vendor services (postgres, redis, etc.)",
    )

    # Core dependencies - following .env-devel and Makefile requirements
    # depends_on("docker@20.10:", type=("build", "run"))
    # depends_on("docker-compose@2.0:", type=("build", "run"))
    # depends_on("git@2.0:", type="build")
    # depends_on("make@4.2:", type="build")
    # depends_on("jq@1.6:", type="build")
    # depends_on("gawk@5.0:", type="build")
    # depends_on("curl@7.0:", type="build")
    # depends_on("wget@1.20:", type="build")
    #
    # # Python - following python version requirement
    depends_on("python@3.11", type=("build", "run"))

    # depends_on("py-pip", type="build")
    # depends_on("py-virtualenv", type="build")
    depends_on("uv", type="build")
    #
    # # Node.js for frontend - following package.json
    # depends_on("node-js@18:", type="build", when="+frontend")
    # depends_on("npm@8:", type="build", when="+frontend")
    #
    # # System utilities
    # depends_on("bash@4.0:", type=("build", "run"))
    # depends_on("findutils", type="build")
    # depends_on("sed", type="build")
    #
    # # Testing dependencies
    # depends_on("py-pytest", type="test", when="+tests")
    # depends_on("py-pytest-cov", type="test", when="+tests")
    #
    # # Conflicts
    # conflicts("platform=windows", msg="Windows is not supported.
    # Use WSL2 instead.")
    #
    def setup_build_environment(self, env):
        """Setup build environment variables following .env-devel structure."""
        # Core Docker settings
        env.set("DOCKER_REGISTRY", "local")
        env.set(
            "DOCKER_IMAGE_TAG",
            ("prod" if "+prod" in self.spec else "devel"),
        )
        env.set(
            "SWARM_STACK_NAME",
            f"spack-{self.spec.name}",
        )

        # Python settings
        env.set("PYTHON_VERSION", "3.11")

        # Build configuration
        if "+prod" in self.spec:
            env.set("BUILD_TARGET", "prod")
        else:
            env.set("BUILD_TARGET", "devel")

        # Frontend settings
        if "+frontend" in self.spec:
            env.set("BUILD_FRONTEND", "1")
        else:
            env.set("BUILD_FRONTEND", "0")

        # Set CPU count for parallel builds
        try:
            env.set(
                "DEV_PC_CPU_COUNT",
                str(multiprocessing.cpu_count()),
            )
        except Exception:  # pylint: disable=broad-except
            env.set("DEV_PC_CPU_COUNT", "4")

    def setup_run_environment(self, env):
        """Setup runtime environment variables."""
        env.set(
            "OSPARC_SIMCORE_ROOT",
            self.prefix.share.osparc_simcore,
        )
        env.prepend_path("PATH", join_path(self.prefix, "bin"))

        # Docker swarm settings
        env.set(
            "SWARM_STACK_NAME",
            f"spack-{self.spec.name}",
        )
        env.set("DOCKER_REGISTRY", "local")

        # Service endpoints - following project's nip.io pattern
        env.set(
            "OSPARC_FRONTEND_URL",
            "http://127.0.0.1.nip.io:9081",
        )
        env.set(
            "OSPARC_API_URL",
            "http://127.0.0.1.nip.io:8006",
        )

    @run_before("install")
    def check_prerequisites(self):
        """Check prerequisites following project requirements."""
        # Check Docker daemon
        try:
            subprocess.check_call(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as exc:
            raise InstallError(
                "Docker daemon is not running. Please start Docker first."
            ) from exc

        # Check Docker Swarm (initialize if needed)
        try:
            subprocess.check_call(
                ["docker", "node", "ls"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            tty.msg("Initializing Docker Swarm...")
            subprocess.check_call(["docker", "swarm", "init"])

        # Check Python version matches requirement
        python_exe = self.spec["python"].command.path
        result = subprocess.run(
            [python_exe, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "3.11" not in result.stdout:
            tty.warn(
                "Python version should be 3.11, found: "
                f"{result.stdout.strip()}"
            )

    def install(self, spec, prefix):
        """Install osparc-simcore following project structure."""

        # Create installation directories
        mkdirp(prefix.bin)
        mkdirp(prefix.etc.osparc_simcore)
        mkdirp(prefix.share.osparc_simcore)
        mkdirp(prefix.var.log.osparc_simcore)

        # Copy entire source tree to share directory
        install_tree(
            ".",
            prefix.share.osparc_simcore,
            ignore=lambda files: [
                f
                for f in files
                # if f.startswith(".git")
                if f.endswith(".pyc")
                or f.endswith("__pycache__")
            ],
        )

        # Create environment file following project's env-vars.md guidelines
        self._create_environment_file(prefix)
        with working_dir(prefix.share.osparc_simcore):
            try:
                self.make("devenv")
                tty.msg("Successfully built dev environment")
            except Exception as exception:  # pylint: disable=broad-except
                tty.error("Could not build dev environment during install. ")
                print(traceback.format_exc())
                raise exception

        self._setup_python_environment(prefix)

        # Create wrapper scripts
        self._create_wrapper_scripts(prefix)

        # Build Docker images if in production mode
        if "+prod" in spec:
            with working_dir(prefix.share.osparc_simcore):
                try:
                    # Build production images
                    self.make("build")
                    tty.msg("Successfully built production Docker images")
                except Exception:  # pylint: disable=broad-except
                    tty.warn(
                        "Could not build Docker images during install. "
                        "Run 'osparc-build' manually after installation."
                    )

    def _create_environment_file(self, prefix):
        """Create .env file following project's environment var guidelines."""
        env_file = join_path(prefix.share.osparc_simcore, ".env")

        # Read the template .env-devel file
        env_devel_path = join_path(
            prefix.share.osparc_simcore,
            ".env-devel",
        )

        env_content = f"""# osparc-simcore Spack environment configuration
# Based on .env-devel with Spack-specific modifications

# Core settings
COMPOSE_PROJECT_NAME=spack-simcore
SWARM_STACK_NAME=spack-{self.spec.name}
DOCKER_REGISTRY=local
DOCKER_IMAGE_TAG={"prod" if "+prod" in self.spec else "devel"}

# Installation paths
OSPARC_SIMCORE_ROOT={prefix.share.osparc_simcore}

# Python settings
PYTHON_VERSION=3.11

# Build settings
BUILD_TARGET={"prod" if "+prod" in self.spec else "devel"}
DEV_PC_CPU_COUNT={os.cpu_count() or 4}

# Service URLs (using nip.io for local development)
SIMCORE_WEB_OUTDIR={prefix.share.osparc_simcore}/services/static-webserver/client/source-output
"""

        # Merge with existing .env-devel if it exists
        if os.path.exists(env_devel_path):
            with open(env_devel_path, "r", encoding="utf-8") as f:
                devel_content = f.read()

            # Filter out conflicting variables
            filtered_lines = []
            skip_vars = {
                "COMPOSE_PROJECT_NAME",
                "SWARM_STACK_NAME",
                "DOCKER_REGISTRY",
                "DOCKER_IMAGE_TAG",
                "BUILD_TARGET",
            }

            for line in devel_content.split("\n"):
                if "=" in line and not line.startswith("#"):
                    var_name = line.split("=")[0].strip()
                    if var_name not in skip_vars:
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)

            env_content += "\n# From .env-devel\n" + "\n".join(filtered_lines)

        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)

    def _setup_python_environment(self, prefix):
        """Setup Python virtual environment using uv."""

        with working_dir(prefix.share.osparc_simcore):
            # Create virtual environment using uv
            uv_exe = which("uv")
            if uv_exe:
                uv_exe(
                    "venv",
                    ".venv",
                    "--python",
                    "3.11",
                )
            else:
                # Fallback to standard venv
                python_exe = self.spec["python"].command.path
                subprocess.check_call(
                    [
                        python_exe,
                        "-m",
                        "venv",
                        ".venv",
                    ]
                )

    def _create_wrapper_scripts(self, prefix):
        """Create wrapper scripts for osparc-simcore operations."""

        # Base script template
        script_template = f"""#!/bin/bash
# osparc-simcore wrapper script generated by Spack

set -euo pipefail

export OSPARC_SIMCORE_ROOT="{prefix.share.osparc_simcore}"
export PATH="{prefix.share.osparc_simcore}/.venv/bin:$PATH"

# Source environment
if [ -f "$OSPARC_SIMCORE_ROOT/.env" ]; then
    set -o allexport
    source "$OSPARC_SIMCORE_ROOT/.env"
    set +o allexport
fi

cd "$OSPARC_SIMCORE_ROOT"

# Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running" >&2
    exit 1
fi

# Check Docker Swarm
if ! docker node ls >/dev/null 2>&1; then
    echo "Initializing Docker Swarm..."
    docker swarm init
fi
"""

        # Main osparc command
        main_script = join_path(prefix.bin, "osparc")
        with open(main_script, "w", encoding="utf-8") as f:
            f.write(
                script_template
                + """
# Execute make command
exec make "$@"
"""
            )
        os.chmod(main_script, 0o755)

        # Build command
        build_script = join_path(prefix.bin, "osparc-build")
        with open(build_script, "w", encoding="utf-8") as f:
            f.write(
                script_template
                + f"""
echo "Building osparc-simcore Docker images..."
exec make {"build" if "+prod" in self.spec else "build-devel"}
"""
            )
        os.chmod(build_script, 0o755)

        # Deploy commands
        deploy_script = join_path(prefix.bin, "osparc-up")
        with open(deploy_script, "w", encoding="utf-8") as f:
            f.write(
                script_template
                + f"""
echo "Deploying osparc-simcore..."
exec make {"up-prod" if "+prod" in self.spec else "up-devel"}
{"ops_disabled=1" if "~ops" in self.spec else ""}
"""
            )
        os.chmod(deploy_script, 0o755)

        # Stop command
        stop_script = join_path(prefix.bin, "osparc-down")
        with open(stop_script, "w", encoding="utf-8") as f:
            f.write(
                script_template
                + """
echo "Stopping osparc-simcore..."
exec make down
"""
            )
        os.chmod(stop_script, 0o755)

        # Info command
        info_script = join_path(prefix.bin, "osparc-info")
        with open(info_script, "w", encoding="utf-8") as f:
            f.write(
                script_template
                + f"""
echo "osparc-simcore installation info:"
echo "Installation root: $OSPARC_SIMCORE_ROOT"
echo "Variant: {"prod" if "+prod" in self.spec else "devel"}"
echo ""
exec make info show-endpoints
"""
            )
        os.chmod(info_script, 0o755)

        # Test command (when +tests variant is enabled)
        if "+tests" in self.spec:
            test_script = join_path(prefix.bin, "osparc-test")
            with open(test_script, "w", encoding="utf-8") as f:
                f.write(
                    script_template
                    + """
echo "Running osparc-simcore tests..."
exec make test-unit
"""
                )
            os.chmod(test_script, 0o755)

    @run_after("install")
    def post_install_message(self):
        """Display post-installation information following guidelines."""
        tty.msg("🎉 osparc-simcore has been installed successfully!")
        tty.msg("")
        tty.msg("Available commands:")
        tty.msg("  osparc        - Run any make target")
        tty.msg("  osparc-build  - Build Docker images")
        tty.msg("  osparc-up     - Deploy and start services")
        tty.msg("  osparc-down   - Stop services")
        tty.msg("  osparc-info   - Show system info and endpoints")
        if "+tests" in self.spec:
            tty.msg("  osparc-test   - Run unit tests")
        tty.msg("")
        tty.msg("Quick start:")
        tty.msg("  1. Load the package: spack load osparc-simcore")
        tty.msg("  2. Build images:     osparc-build")
        tty.msg("  3. Start platform:   osparc-up")
        tty.msg("  4. Open browser:     http://127.0.0.1.nip.io:9081/")
        tty.msg("")
        tty.msg("For more information: osparc-info")
        tty.msg(f"Installation: {self.prefix.share.osparc_simcore}")

    def test_installation(self):
        """Test the installation following TDD principles."""
        with working_dir(self.prefix.share.osparc_simcore):
            # Test basic make targets
            self.make("info")

            # Test environment setup
            env_file = join_path(
                self.prefix.share.osparc_simcore,
                ".env",
            )
            assert os.path.isfile(env_file), "Environment file not created"

            # Test Python virtual environment
            venv_python = join_path(
                self.prefix.share.osparc_simcore,
                ".venv",
                "bin",
                "python",
            )
            if os.path.isfile(venv_python):
                result = subprocess.run(
                    [venv_python, "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                assert (
                    "3.11" in result.stdout
                ), f"Wrong Python version in venv: {result.stdout}"

        # Test wrapper scripts
        for script in [
            "osparc",
            "osparc-build",
            "osparc-up",
            "osparc-down",
            "osparc-info",
        ]:
            script_path = join_path(self.prefix.bin, script)
            assert os.path.isfile(script_path), f"Script {script} not created"
            assert os.access(
                script_path, os.X_OK
            ), f"Script {script} not executable"

    @property
    def build_directory(self):
        """Use source directory for building."""
        return self.stage.source_path
