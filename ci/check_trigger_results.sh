#! /bin/bash
# Compare a local trigger log to a reference log file

# Check the trigger directory name for the old style
TRIGDIR="mu2e-trig-config/"
if [ ! -d ${TRIGDIR} ]; then
    TRIGDIR="mu2e_trig_config/"
fi

# Process the example data-like digi file
NEVENTS=-1
DATAFILE="${TRIGDIR}ci/data_files.txt"
LOGFILE="local_trigger_results.log"
REFERENCE="${TRIGDIR}ci/reference_log_file.log"
mu2e -c ${TRIGDIR}test/triggerTest.fcl -S ${DATAFILE} -n ${NEVENTS} >| ${LOGFILE}
STATUS=$?

# Add the log to the stdout report
cat ${LOGFILE}

# Check if the processing failed
if [ $STATUS -ne 0 ]; then
    echo ">>> Failed to process triggerTest.fcl"
    exit 2
fi

# Compare the log file to an example log file
python ${TRIGDIR}ci/check_trigger_results.py ${LOGFILE} ${REFERENCE}
STATUS=$?
exit $STATUS
