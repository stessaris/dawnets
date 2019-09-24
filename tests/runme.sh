#!/bin/bash

# Get the path of this script
#   see <https://stackoverflow.com/a/246128>
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Directory within ./runs in which benchmarks are stored
# get the value from ENV if available
BENCHMARK=${BENCHMARK:-${1}}

STDOUTFILE=log_stdout.txt
STDERRFILE=log_stderr.txt

if [[ -n "${BENCHMARK}" && -e "${BENCHMARK}" ]]
then
    RUNDIR=`dirname "${BENCHMARK}"`
    # Get full path <https://stackoverflow.com/a/284667>
    RUNDIR="$(unset CDPATH && cd "$RUNDIR" && pwd)/"
    BENCHMARK=${RUNDIR}$(basename "$BENCHMARK")
elif [[ -d "${SCRIPTDIR}/runs" ]]
then
    # get the most recent directory within the runs
    RUNDIR=`ls -dt "${SCRIPTDIR}"/runs/*/ 2>/dev/null|head -n 1`
    if [[ -n "${RUNDIR}" && -d "${RUNDIR}benchmarks" ]]
    then
        BENCHMARK=${RUNDIR}benchmarks
    else
        echo 1>&2 "No benchmarks in \"${RUNDIR}/benchmarks\""
        exit -1
    fi
else
    echo 1>&2 "No benchmarks in \"${BENCHMARK}\""
    exit -1
fi

cmd="run-dawnets-benchmarks \"${BENCHMARK}\" 1>>\"${RUNDIR}${STDOUTFILE}\" 2>>\"${RUNDIR}${STDERRFILE}\""
echo "`date` Running: cd \"${RUNDIR}\"; $cmd"|tee -a "${RUNDIR}${STDERRFILE}"
cd "${RUNDIR}"
eval exec $cmd