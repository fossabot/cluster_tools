"""Abstracts access to a Slurm cluster via its command-line tools.
"""
import re
import os
import threading
import time
from cluster_tools.util import chcall, random_string, local_filename
from .cluster_executor import ClusterExecutor

SLURM_STATES = {
    "Failure": [
        "CANCELLED",
        "BOOT_FAIL",
        "DEADLINE",
        "FAILED",
        "NODE_FAIL",
        "OUT_OF_MEMORY",
        "PREEMPTED",
        "STOPPED",
        "TIMEOUT"
    ],
    "Success": [
        "COMPLETED"
    ],
    "Ignore": [
        "RUNNING",
        "CONFIGURING",
        "COMPLETING",
        "PENDING",
        "RESV_DEL_HOLD",
        "REQUEUE_FED",
        "REQUEUE_HOLD",
        "REQUEUED",
        "RESIZING"
    ],
    "Unclear": [
        "SUSPENDED",
        "REVOKED",
        "SIGNALING",
        "SPECIAL_EXIT",
        "STAGE_OUT"
    ]
}


def submit_text(job, job_name):
    """Submits a Slurm job represented as a job file string. Returns
    the job ID.
    """
    job_name_arg = ""
    if job_name is not None:
        job_name_arg = '--job-name "{}"'.format(job_name)

    filename = local_filename("_temp_{}.sh".format(random_string()))
    with open(filename, "w") as f:
        f.write(job)
    jobid, _ = chcall("sbatch {} --parsable {}".format(job_name_arg, filename))
    os.unlink(filename)
    return int(jobid)


class SlurmExecutor(ClusterExecutor):

    def format_log_file_name(jobid):
        return local_filename("slurmpy.stdout.{}.log").format(str(jobid))

    def inner_submit(
        self,
        cmdline,
        outpath_fmt=OUTFILE_FMT,
        job_name=None,
        additional_setup_lines=[],
        job_count=None,
    ):
        """Starts a Slurm job that runs the specified shell command line.
        """

        outpath = outpath_fmt.format("%j" if job_count is None else "%A.%a")

        job_resources_lines = []
        if self.job_resources is not None:
            for resource, value in self.job_resources.items():
                job_resources_lines += ["#SBATCH --{}={}".format(resource, value)]

        job_array_line = ""
        if job_count is not None:
            job_array_line = "#SBATCH --array=0-{}".format(job_count - 1)

        script_lines = (
            ["#!/bin/sh", "#SBATCH --output={}".format(outpath), job_array_line]
            + job_resources_lines
            + [*additional_setup_lines, "srun {}".format(cmdline)]
        )

        return submit_text("\n".join(script_lines), job_name)