# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os

import aiokef

# -- Project information -----------------------------------------------------

project = "aiokef"
copyright = "2019, Bas Nijholt"
author = "Bas Nijholt"
version = aiokef.__version__
release = aiokef.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.viewcode",  # View source code from documentation pages
    "sphinx.ext.napoleon",  # numpy-style docstrings
    "sphinxcontrib.apidoc",  # Run sphinx-apidoc when building
    "m2r",
]
# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

default_role = "autolink"

# -- Extension configuration -------------------------------------------------

napoleon_google_docstring = False

autosummary_generate = True

apidoc_module_dir = os.path.dirname(aiokef.__file__)
apidoc_output_dir = "reference"
apidoc_separate_modules = True
apidoc_toc_file = False
apidoc_module_first = True
apidoc_extra_args = ["--force"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# The license file has no extension, so Sphinx ignores it by default, so we
# must add it here
html_extra_path = ["LICENSE"]
