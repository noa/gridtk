#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""The main entry for bob ip binseg (click-based) scripts."""

import click

from bob.extension.scripts.click_helper import AliasedGroup, verbosity_option

import logging
logger = logging.getLogger(__name__)


def __idiap_setup__():
    """Sets up access to Idiap's SoGE implementation, if available"""

    import os
    lib = '/idiap/resource/software/sge/stable/lib/lx-amd64/libdrmaa.so'
    if os.path.exists(lib):
        logger.debug(f"At Idiap, setting up SoGE library at {lib}...")
        os.environ['DRMAA_LIBRARY_PATH'] = lib
        import drmaa


@click.group(cls=AliasedGroup)
def grid():
    """HPC Job Manager"""
    __idiap_setup__()


@grid.command(
    epilog="""Examples:

\b
    1. List all jobs executing right now on your behalf:

       $ bob grid list

""",
)
@verbosity_option()
def list(verbose, **kwargs):
    """Lists submitted jobs
    """

    from ..list import list
    list()
