from setuptools import setup, find_packages
import re
import codecs
import os
import subprocess


# Hack to allow non-normalised versions
#   see <https://github.com/pypa/setuptools/issues/308>
from setuptools.extern.packaging import version
version.Version = version.LegacyVersion

_INCLUDE_GIT_REV_ = True


# see <https://stackoverflow.com/a/39671214> and 
#     <https://packaging.python.org/guides/single-sourcing-package-version>
def find_version(*pkg_path):
    pkg_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), *pkg_path)
    version_file = codecs.open(os.path.join(pkg_dir, '__init__.py'), 'r').read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if _INCLUDE_GIT_REV_:
        try:
            _git_revision_ = subprocess.check_output(['git', 'describe', '--always', '--dirty']).decode("utf-8").strip()
        except subprocess.CalledProcessError:
            _git_revision_ = None
    if version_match:
        return version_match.group(1) + ('' if _git_revision_ is None else '+' + _git_revision_)
    elif _git_revision_ is not None:
        return _git_revision_
    raise RuntimeError("Unable to find version string.")


setup(
    name='dawnets',
    version=find_version('dawnet'),
    description='DAWNets encoding tools',
    url='https://gitlab.inf.unibz.it/RAW-SYS/workflow-planning',
    author='Sergio Tessaris',
    author_email='tessaris@inf.unibz.it',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click==7.0',    # CLI library
        'py-cpuinfo==5.0.0',  # to get HW details
        'future==0.17.1',   # Python 2/3 compatibility
        'Jinja2==2.11.3',   # Template library
        'jsonschema==3.0.2',
        'psutil==5.6.3',   # to get HW details
        'ruamel.yaml==0.16.5',
        'textx==2.0.1'     # Parser for guard expressions
    ],
    exclude_package_data={'': ['.gitignore']},
    scripts=['coala-clingo'],
    entry_points='''
        [console_scripts]
        dawnets=dawnet.cli:main
    '''
)
