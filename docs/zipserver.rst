=========
zipserver
=========

---------------------
Simple ZIP fileserver
---------------------

:Author: Louis-Philippe Véronneau
:Date: 2021
:Manual section: 1

Synopsis
========

| zipserver [**--bind** ADDRESS] [**--directory** DIRECTORY] *<port>*
| zipserver (**-h** \| **--help**)

Description
===========

**zipserver** is a simple fileserver with support for downloading multiple
files and folders as a single zip file.

Arguments
=========

| *<port>*       Specify alternate port. Default: 8000

Options
=======

| **-h** **--help**  Shows the help message
| **-b** **--bind**  Specify alternate bind address. Default: all interfaces
| **--directory**    Specify alternative directory. Default: current directory

Bugs
====

Bugs can be reported to your distribution's bug tracker or upstream
at https://github.com/pR0Ps/zipstream-ng/issues.
