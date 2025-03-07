#! /bin/bash
# Compare a local trigger log to a reference log file

# Process the example data-like digi file
NEVENTS=-1
DATAFILE="mu2e-trig-config/ci/data_files.txt"
LOGFILE="local_trigger_results.log"
REFERENCE="mu2e-trig-config/ci/reference_log_file.log"
mu2e -c mu2e-trig-config/test/triggerTest.fcl -S ${DATAFILE} -n ${NEVENTS} >| ${LOGFILE}
STATUS=$?

# Add the log to the stdout report
cat ${LOGFILE}

# Check if the processing failed
if [ $STATUS -ne 0 ]; then
    echo ">>> Failed to process triggerTest.fcl"
    exit 2
fi

# Compare the log file to an example log file
python mu2e-trig-config/ci/check_trigger_results.py ${LOGFILE} ${REFERENCE}
STATUS=$?
exit $STATUS
