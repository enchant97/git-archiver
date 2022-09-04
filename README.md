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

```

## License
This project is Copyright (c) 2022 Leo Spratt, licences shown below:

Code

    Apache License - Version 2.0. Full license found in `LICENSE.txt`
