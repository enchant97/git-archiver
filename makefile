IMAGE_NAME := "git-archiver"
VENV_NAME := ".build-venv"

help:
	@echo "-- Building --"
	@echo "build-all"
	@echo "build-package"
	@echo "build-executable"
	@echo "build-docker"
	@echo "-- Utils --"
	@echo "clean"

build-venv:
	@python -m venv ${VENV_NAME}

build-all: build-package build-executable build-docker

build-package: build-venv
	@${VENV_NAME}/bin/python -m pip install -U build
	@${VENV_NAME}/bin/python -m build
	@echo "python package built, outputed into: dist/"

build-executable: build-venv
	@${VENV_NAME}/bin/python -m pip install -U pyinstaller[encryption] -r requirements.txt
	@${VENV_NAME}/bin/pyinstaller -F git-archiver.py --key git-archiver
	@echo "python executable built, written to: dist/git-archiver"

build-docker:
	@docker build -t ${IMAGE_NAME} .
	@echo "docker image built, called: ${IMAGE_NAME}"

clean:
	@rm -rf dist/ build/ *.spec *.egg-info ${VENV_NAME}
