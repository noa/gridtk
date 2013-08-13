#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Wed 24 Aug 2011 13:06:25 CEST

"""Defines the job manager which can help you managing submitted grid jobs.
"""

from __future__ import print_function

import subprocess
import time
import copy, os, sys

import gdbm, anydbm
from cPickle import dumps, loads

from .tools import makedirs_safe, logger


from .manager import JobManager
from .models import add_job, Job

class JobManagerLocal(JobManager):
  """Manages jobs run in parallel on the local machine."""
  def __init__(self, **kwargs):
    """Initializes this object with a state file and a method for qsub'bing.

    Keyword parameters:

    statefile
      The file containing a valid status database for the manager. If the file
      does not exist it is initialized. If it exists, it is loaded.

    """
    JobManager.__init__(self, **kwargs)


  def submit(self, command_line, name = None, array = None, dependencies = [], log_dir = None, dry_run = False, stop_on_failure = False, **kwargs):
    """Submits a job that will be executed on the local machine during a call to "run".
    All kwargs will simply be ignored."""
    # add job to database
    self.lock()
    job = add_job(self.session, command_line=command_line, name=name, dependencies=dependencies, array=array, log_dir=log_dir, stop_on_failure=stop_on_failure)
    logger.info("Added job '%s' to the database" % job)

    if dry_run:
      print("Would have added the Job", job, "to the database to be executed locally.")
      self.session.delete(job)
      logger.info("Deleted job '%s' from the database due to dry-run option" % job)
      job_id = None
    else:
      job_id = job.id

    # return the new job id
    self.unlock()
    return job_id


  def resubmit(self, job_ids = None, failed_only = False, running_jobs = False):
    """Re-submit jobs automatically"""
    self.lock()
    # iterate over all jobs
    jobs = self.get_jobs(job_ids)
    accepted_old_status = ('failure',) if failed_only else ('success', 'failure')
    for job in jobs:
      # check if this job needs re-submission
      if running_jobs or job.status in accepted_old_status:
        # re-submit job to the grid
        logger.info("Re-submitted job '%s' to the database" % job)
        job.submit('local')

    self.session.commit()
    self.unlock()


  def stop_jobs(self, job_ids):
    """Stops the jobs in the grid."""
    self.lock()

    jobs = self.get_jobs(job_ids)
    for job in jobs:
      if job.status == 'executing':
        logger.info("Reset job '%s' in the database" % job)
        job.status = 'submitted'

    self.session.commit()
    self.unlock()

  def stop_job(self, job_id, array_id = None):
    """Stops the jobs in the grid."""
    self.lock()

    job, array_job = self._job_and_array(job_id, array_id)
    if job.status == 'executing':
      logger.info("Reset job '%s' in the database" % job)
      job.status = 'submitted'

    if array_job is not None and array_job.status == 'executing':
      logger.debug("Reset array job '%s' in the database" % array_job)
      array_job.status = 'submitted'

    self.session.commit()
    self.unlock()


#####################################################################
###### Methods to run the jobs in parallel on the local machine #####

  def _run_parallel_job(self, job_id, array_id = None):
    """Executes the code for this job on the local machine."""
    environ = copy.deepcopy(os.environ)
    environ['JOB_ID'] = str(job_id)
    if array_id:
      environ['SGE_TASK_ID'] = str(array_id)
    else:
      environ['SGE_TASK_ID'] = 'undefined'

    # generate call to the wrapper script
    command = [self.wrapper_script, '-ld', self._database, 'run-job']

    logger.info("Started execution of Job '%s'" % self._format_log(job_id, array_id))

    # return the subprocess pipe to the process
    try:
      return subprocess.Popen(command, env=environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
      logger.error("Could not execute job '%s' locally, reason:\n\t%s" % self._format_log(job_id, array_id), e)
      return None


  def _result_files(self, process, job_id, array_id = None, no_log = False):
    """Finalizes the execution of the job by writing the stdout and stderr results into the according log files."""
    def write(file, std, process):
      f = std if file is None else open(str(file), 'w')
      f.write(process.read())

    self.lock()
    # get the files to write to
    job, array_job = self._job_and_array(job_id, array_id)
    if no_log:
      out, err = None, None
    elif array_job:
      out, err = array_job.std_out_file(), array_job.std_err_file()
    else:
      out, err = job.std_out_file(), job.std_err_file()

    log_dir = job.log_dir if not no_log else None
    job_id = job.id
    array_id = array_job.id if array_job else None
    self.unlock()

    if log_dir:
      makedirs_safe(log_dir)

    # write stdout
    write(out, sys.stdout, process.stdout)
    # write stderr
    write(err, sys.stderr, process.stderr)

    if log_dir:
      j = self._format_log(job_id, array_id)
      logger.debug("Wrote output of job '%s' to file '%s'" % (j,out))
      logger.debug("Wrote errors of job '%s' to file '%s'" % (j,err))


  def _format_log(self, job_id, array_id = None):
    return ("%d (%d)" % (job_id, array_id)) if array_id is not None else ("%d" % job_id)

  def run_scheduler(self, parallel_jobs = 1, job_ids = None, sleep_time = 0.1, die_when_finished = False, no_log = False):
    """Starts the scheduler, which is constantly checking for jobs that should be ran."""
    running_tasks = []
    try:

      while True:
        # Flag that might be set in some rare cases, and that prevents the scheduler to die
        repeat_execution = False
        # FIRST, try if there are finished processes; this does not need a lock
        for task_index in range(len(running_tasks)-1, -1, -1):
          task = running_tasks[task_index]
          process = task[0]
          if process.poll() is not None:
            # process ended
            job_id = task[1]
            array_id = task[2] if len(task) > 2 else None
            # report the result
            self._result_files(process, job_id, array_id, no_log)
            logger.info("Job '%s' finished execution" % self._format_log(job_id, array_id))

            # in any case, remove the job from the list
            del running_tasks[task_index]

        # SECOND, check if new jobs can be submitted; THIS NEEDS TO LOCK THE DATABASE
        if len(running_tasks) < parallel_jobs:
          # get all unfinished jobs:
          self.lock()
          jobs = self.get_jobs(job_ids)
          # put all new jobs into the queue
          for job in jobs:
            if job.status == 'submitted':
              job.queue()

          # get all unfinished jobs that are submitted to the local queue
          unfinished_jobs = [job for job in jobs if job.status in ('queued', 'executing') and job.queue_name == 'local']
          for job in unfinished_jobs:
            if job.array:
              # find array jobs that can run
              queued_array_jobs = [array_job for array_job in job.array if array_job.status == 'queued']
              if not len(queued_array_jobs):
                job.finish(0, -1)
                repeat_execution = True
              else:
                # there are new array jobs to run
                for i in range(min(parallel_jobs - len(running_tasks), len(queued_array_jobs))):
                  array_job = queued_array_jobs[i]
                  # start a new job from the array
                  process = self._run_parallel_job(job.id, array_job.id)
                  running_tasks.append((process, job.id, array_job.id))
                  # we here set the status to executing manually to avoid jobs to be run twice
                  # e.g., if the loop is executed while the asynchronous job did not start yet
                  array_job.status = 'executing'
                  job.status = 'executing'
                  if len(running_tasks) == parallel_jobs:
                    break
            else:
              if job.status == 'queued':
                # start a new job
                process = self._run_parallel_job(job.id)
                running_tasks.append((process, job.id))
                # we here set the status to executing manually to avoid jobs to be run twice
                # e.g., if the loop is executed while the asynchronous job did not start yet
                job.status = 'executing'
            if len(running_tasks) == parallel_jobs:
              break

          self.session.commit()
          self.unlock()

        # if after the submission of jobs there are no jobs running, we should have finished all the queue.
        if die_when_finished and not repeat_execution and len(running_tasks) == 0:
          logger.info("Stopping task scheduler since there are no more jobs running.")
          break

        # THIRD: sleep the desired amount of time before re-checking
        time.sleep(sleep_time)

    # This is the only way to stop: you have to interrupt the scheduler
    except KeyboardInterrupt:
      logger.info("Stopping task scheduler due to user interrupt.")
      for task in running_tasks:
        logger.warn("Killing job '%s' that was still running." % self._format_log(task[1], task[2] if len(task) > 2 else None))
        task[0].kill()
        self.stop_job(task[1], task[2] if len(task) > 2 else None)