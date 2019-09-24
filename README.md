
# DAWNets encoding tool

Tools to encode DAWNets reachability problem into planning and model checking verification problems

## Getting Started

### Using Docker

Requirements and packages can be installed using [Docker](https://docs.docker.com/get-started/). The provided `Dockerfile` installs also the planners and model checker tools.

To create the image you should run the `build` command:

```
$ docker build -t <tag_name> .
```

and then access the container using

```
$ docker run --rm  -it <tag_name>
Usage: dawnets [OPTIONS] COMMAND [ARGS]...

  Encode DAWNet reachability problems. To see the commands usage run
  'command' --help

Options:
  --version              Show the version and exit.
  -c, --config FILENAME  Configuration file
  -s, --solve            Solve the problem using the appropriate tool
  -k, --keep             Keep intermediate files
  -v, --verbose          Increase logging verbosity
  --stdout FILENAME      Redirect standard output to file
  --stderr FILENAME      Redirect standard error to file
  --tmpdir DIRECTORY     Directory for temporary files
  --timeout INTEGER      Stop the solver after the number of seconds
  --memlimit INTEGER     Limit the amount of memory for the solver (in bytes)
  --stats PATH           Solver stats are written in this file
  --logfile PATH         Logs are written in this file
  --usejson              Use JSON parser to read input files
  --help                 Show this message and exit.

Commands:
  benchmark  Generates a benchmark based on the given...
  coala      Generates a Coala encoding of the model.
  config     Shows the configuration options
  dot        Generates a Graphviz representation of the...
  nusmv      Generates a nuSMV encoding of the model.
  pddl       Generates a PDDL encoding of the model.
  run        Run the given benchmarks described as YAML...
  runcmd     Execute the given command
  show       Print a description of the model.
  trace      Output a model augmented with the given...
  validate   Read the model to check whether it's well...
```

To run the tests described in the file `tests/benchmarks-desc.yaml` the command should be
```bash
cd tests
docker run --rm -v "`pwd`":/dawnets -w /dawnets -it dawnets run benchmarks-desc.yaml
```

By default the image uses the `dawnets` entry point, to override it you can set the `--entrypoint` option; e.g.
```
docker run --rm --entrypoint bash -it dawnets
dawnet@76e090ab5b96:/usr/local/src/dawnets$ pwd
/usr/local/src/dawnets
```

To access the host local folder you can use the `-v` option:

```
docker run --rm --entrypoint bash -v "`pwd`":/dawnets -w /dawnets -it dawnets
dawnet@8806db989ce2:/dawnets$ ls
Dockerfile  MANIFEST.in  Makefile  Pipfile  Pipfile.lock  README.md  dawnet  dawnets  dawnets.egg-info  dawnets_evaluation  requirements.txt  run-dawnets-benchmarks  setup.cfg  setup.py  tests
```

#### Using make

The included `Makefile` contains a `docker` rule for building an image and a `run` rule that starts a container with a bash shell. In order to use the automatic build your machine needs `make` and `setuptools` for the default Python (e.g. they are not necessarily installed by default in Linux distros). 

### Manual install

The tool is written in Python, it should be compatible with both 2.7 and 3.x Python versions. However the *Coala planner* (see below) is not yet compatible with Python 3.

#### Prerequisites

You need a working Python installation with [pip](https://pip.readthedocs.io/en/stable/) package management tool, and [pipenv](https://docs.pipenv.org/install/). The latter can be installed using `pip`:

```
pip install pipenv
```

In addition, to verify reachability you need the following tools

* [Coala planner](https://github.com/potassco/coala) (requires [Clingo](https://github.com/potassco/clingo/blob/master/INSTALL.md))
* [FastDownward planner](http://www.fast-downward.org/ObtainingAndRunningFastDownward)
* [nuXmv model checker](https://es-static.fbk.eu/tools/nuxmv/)

#### Installing

To avoid polluting your Python library the tool should be installed in a virtual environment using `pipenv`:

```
$ mkdir ${install_dir}
$ cd ${install_dir}
$ pipenv install
```

On OS X you might get an error due to a bad locale settings, to fix it you need to set the following environment variables:

```
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

More details are available on `pipenv` issues [538](https://github.com/pypa/pipenv/issues/538) and [187](https://github.com/pypa/pipenv/issues/187).

To activate the environment is enough to run the `pipenv shell` command within the `${install_dir}`, then the tool will be available as the script `dawnets`:

```
$ pipenv shell
Spawning environment shell (/bin/bash). Use 'exit' to leave.
source .......
..............
$ dawnets
Usage: dawnets [OPTIONS] COMMAND [ARGS]...

  Encode DAWNet reachability problems. To see the commands usage run
  'command' --help

Options:
  --help  Show this message and exit.

Commands:
  coala     Generates a Coala encoding of the model.
  dot       Generates a Graphviz representation of the...
  pddl      Generates a PDDL encoding of the model.
  show      Print a description of the model.
  trace     Output a model augmented with the given...
  validate  Read the model to check whether it's well...
```
Alternatively the `pipenv run` command can be used to run the tool without entering a separate subshell:

```
$ pipenv run dawnets dot --help
Usage: cli.py dot [OPTIONS] MODEL [TRACE]

  Generates a Graphviz representation of the model. If the trace is given
  then it's incorporated into the model.

Options:
  -o, --outfile FILENAME  output file
  --help                  Show this message and exit.
```

## Running experiments

The source files include a directory (`experiments`) with the description of a set of experiments that have been carried out for publication. Please refer to the `experiments/README.md` file for details.


## Changelog

* **2019-09-?? Version 1.0**: reorganisation of the experiment code for public release
* **2019-01-17 Version 0.9.0**: possibility of generating problems without data
* **2018-09-11 Version 0.8.0**: new PDDL encoding (as technical report) and domain reduction based on guard constants (*works* only without inequalities!)
* **2018-08-31 Version 0.7.3**: rewritten subprocess interface and robustness of trace handling
* **2018-08-23 Version 0.7.2**: changes to the Docker container definition
* **2018-0 Version 0.7.1**: minor fixes to benchmarks generator
* **2018-08-01 Version 0.7.0**: new code for benchmark generation
* **2018-03-08 Version 0.6.0**: added the possibility of using JSON parser (YAML parser was too slow on big models), fixed problem related to [EasyProcess](https://pypi.python.org/pypi/EasyProcess) timeout handling
* **2018-02-15 Version 0.5.2**: added logging to file
* **2018-02-15 Version 0.5.1**: better reporting and macro expansion in automated benchmark reporting, read benchmarks descriptions from folders
* **2018-02-02 Version 0.2**: first tests with Docker


## Authors

* **Sergio Tessaris** - *scripts* 


## License

_#TODO_
