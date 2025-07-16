![Unit Tests](https://github.com/kalanjiyam-org/kalanjiyam/actions/workflows/basic-tests.yml/badge.svg)


Kalanjiyam
==========

Kalanjiyam is an online Siddha Knowledge Systems library whose mission is to make Siddha
literature and knowledge accessible to all. Our library is hosted at https://kalanjiyam.org.

This repository contains Kalanjiyam's core code. It also includes *seed* scripts,
which will automatically pull external data sources and populate a development
database.


Quickstart
----------

(This setup process requires Docker. If you don't have Docker installed on your
machine, you can install it [here][docker].)

To install and run Kalanjiyam locally, please run the commands below:

```
$ git clone https://github.com/kalanjiyam-org/kalanjiyam.git
$ cd kalanjiyam
$ make devserver
```

Then, navigate to `http://localhost:5000` in your web browser.

[docker]: https://docs.docker.com/get-docker/


Documentation
-------------

A full technical reference for this repository can be found here:

https://kalanjiyam.readthedocs.io/en/latest/

It includes installation instructions, architecture notes, and other reference
documentation about Kalanjiyam's technical design.


Contributing
------------

For details on how to contribute to Kalanjiyam, see [`CONTRIBUTING.md`][CONTRIBUTING.md]. We also
strongly recommend joining our [Discord channel][discord], where we have an
ongoing informal discussion about Kalanjiyam's technical problems and roadmap.

[discord]: https://discord.gg/7rGdTyWY7Z
[CONTRIBUTING.md]: /CONTRIBUTING.md
