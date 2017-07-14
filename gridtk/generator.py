#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for generating configurations for running experiments in batch'''


import collections
import itertools

import yaml
import jinja2


def _ordered_load(stream, Loader=yaml.Loader,
    object_pairs_hook=collections.OrderedDict):
  '''Loads the contents of the YAML stream into :py:class:`collection.OrderedDict`'s

  See: https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts

  '''

  class OrderedLoader(Loader): pass

  def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return object_pairs_hook(loader.construct_pairs(node))

  OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
      construct_mapping)

  return yaml.load(stream, OrderedLoader)


def expand(data):
  '''Generates configuration sets based on the YAML input contents

  For an introduction to the YAML mark-up, just search the net. Here is one of
  its references: https://en.wikipedia.org/wiki/YAML

  A configuration set corresponds to settings for **all** variables in the
  input template that needs replacing. For example, if your template mentions
  the variables ``name`` and ``version``, then each configuration set should
  yield values for both ``name`` and ``version``.

  For example:

  .. code-block:: yaml

     name: [john, lisa]
     version: [v1, v2]


  This should yield to the following configuration sets:

  .. code-block:: python

     [
       {'name': 'john', 'version': 'v1'},
       {'name': 'john', 'version': 'v2'},
       {'name': 'lisa', 'version': 'v1'},
       {'name': 'lisa', 'version': 'v2'},
     ]


  Each key in the input file should correspond to either an object or a YAML
  array. If the object is a list, then we'll iterate over it for every possible
  combination of elements in the lists. If the element in question is not a
  list, then it is considered unique and repeated for each yielded
  configuration set. Example

  .. code-block:: yaml

     name: [john, lisa]
     version: [v1, v2]
     text: >
        hello,
        world!

  Should yield to the following configuration sets:

  .. code-block:: python

     [
       {'name': 'john', 'version': 'v1', 'text': 'hello, world!'},
       {'name': 'john', 'version': 'v2', 'text': 'hello, world!'},
       {'name': 'lisa', 'version': 'v1', 'text': 'hello, world!'},
       {'name': 'lisa', 'version': 'v2', 'text': 'hello, world!'},
     ]

  Keys starting with one `_` (underscore) are treated as "unique" objects as
  well. Example:

  .. code-block:: yaml

     name: [john, lisa]
     version: [v1, v2]
     _unique: [i1, i2]

  Should yield to the following configuration sets:

  .. code-block:: python

     [
       {'name': 'john', 'version': 'v1', '_unique': ['i1', 'i2']},
       {'name': 'john', 'version': 'v2', '_unique': ['i1', 'i2']},
       {'name': 'lisa', 'version': 'v1', '_unique': ['i1', 'i2']},
       {'name': 'lisa', 'version': 'v2', '_unique': ['i1', 'i2']},
     ]


  Parameters:

    data (str): YAML data to be parsed


  Yields:

    dict: A dictionary of key-value pairs for building the templates

  '''

  data = _ordered_load(data, yaml.SafeLoader)

  # separates "unique" objects from the ones we have to iterate
  # pre-assemble return dictionary
  iterables = collections.OrderedDict()
  unique = collections.OrderedDict()
  for key, value in data.items():
    if isinstance(value, list) and not key.startswith('_'):
      iterables[key] = value
    else:
      unique[key] = value

  # generates all possible combinations of iterables
  for values in itertools.product(*iterables.values()):
    retval = collections.OrderedDict(unique)
    keys = list(iterables.keys())
    retval.update(dict(zip(keys, values)))
    yield retval


def generate(variables, template):
  '''Yields a resolved "template" for each config set and dumps on output

  This function will extrapolate the ``template`` file using the contents of
  ``variables`` and will output individual (extrapolated, expanded) files in
  the output directory ``output``.


  Parameters:

    variables (str): A string stream containing the variables to parse, in YAML
      format as explained on :py:func:`expand`.

    template (str): A string stream containing the template to extrapolate


  Yields:

    str: A generated template you can save

  '''

  env = jinja2.Environment()
  for c in expand(variables):
    yield env.from_string(template).render(c)


def aggregate(variables, template):
  '''Generates a resolved "template" for **all** config sets and returns

  This function will extrapolate the ``template`` file using the contents of
  ``variables`` and will output a single (extrapolated, expanded) file.


  Parameters:

    variables (str): A string stream containing the variables to parse, in YAML
      format as explained on :py:func:`expand`.

    template (str): A string stream containing the template to extrapolate


  Returns:

    str: A generated template you can save

  '''

  env = jinja2.Environment()
  d = {'cfgset': list(expand(variables))}
  return jinja2.Environment().from_string(template).render(d)
