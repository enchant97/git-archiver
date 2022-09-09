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
                main.<archive-type>
            tags/
            git-archiver.<archive-type>
            git-archiver.bundle

```

## Install
There are many ways of installing and running a Python app. These are the recommended methods.

### pipx
[pipx](https://pypa.github.io/pipx/) is used when you want it installed on the system for a user.

```
python3 -m pip install --user pipx
python3 -m pipx ensurepath

pipx install git+https://github.com/enchant97/git-archiver.git

git-archiver --help
```

## Docker
This method allows running the program inside a docker container.

```
docker build -t git-archiver .

docker run --rm -it git-archiver <app args here>
```

## License
This project is Copyright (c) 2022 Leo Spratt, licences shown below:

Code

    Apache License - Version 2.0. Full license found in `LICENSE.txt`
