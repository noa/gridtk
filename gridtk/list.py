#!/usr/bin/env python
# coding=utf-8

"""Accesses and list job information"""

import logging
logger = logging.getLogger(__name__)

import drmaa


def jobs(users=None, hosts=None, queues=None):
    """Returns a dictionary with all jobs running

    Parameters
    ==========

    users : :py:class:`list`, Optional
        A list of usernames to search jobs for.  If passed, then filters the
        return list with jobs from this particular user.

    hosts : :py:class:`list`, Optional
        A list of hosts to search jobs for.  If passed, then filters the
        return list with jobs for this particular hosts.

    queues : :py:class:`list`, Optional
        A list of queues to search jobs for.  If passed, then filters the
        return list with jobs for this particular queues.

    """

    with drmaa.Session() as s:
      logger.debug('DRMAA session started')
      __import__('ipdb').set_trace()
      pass
