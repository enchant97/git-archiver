# Git Archiver
A tool designed to mass archive a collection of git repositories on a file system into a format that can be put into "cold storage".

> This project is still early in development

## Archived Format
When running an archive into specific structure, shown below:

```
dst/
    enchant97/
        git-archiver/
            branches/
                pre.<archive-type>
            tags/
            all.bundle
            HEAD.<archive-type>
            meta.json
```

## Install
There are many ways of installing and running this app.

### pipx (Recommended)
Install using [pipx](https://pypa.github.io/pipx/), allowing for a self contained user install.

> This will require Python to be installed.

```
pipx install git-archiver
```

### Native Executable
This is the easiest way of using/distributing. Currently you will have to build an executable yourself, documented in the building section.

### Docker
This method allows running the program inside a docker container.

```
docker run --rm -it ghcr.io/enchant97/git-archiver <archiver args here>
```

## Building
You can simply run the makefile to produce different builds.

```
make help
```

## License
This project is Copyright (c) 2022 Leo Spratt, licences shown below:

Code

    Apache License - Version 2.0. Full license found in `LICENSE.txt`
