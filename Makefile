# Create a wheel package and drop it on a web server
#   packages can be installed using
#     pip install --find-links='wheelhouse_url' pkg_name
# see also <https://unrouted.io/2016/07/21/use-make/>

PIPENV := pipenv
PIP := pip
PYTHON := python
DOCKER := docker
TAR := tar
GIT := git

CWD := $(shell pwd)
NAME = $(shell $(PYTHON) setup.py --name)
VERSION = $(shell $(PYTHON) setup.py --version)

DNAME := $(NAME)
# docker tags don't allow '+'
DTAG := $(subst +,_,$(VERSION))
DOCKERFILE := Dockerfile
DOCKER_CONTEXT := .

.PHONY: docker
docker: $(DOCKERFILE)
	$(DOCKER) build -t $(DNAME):latest -t $(DNAME):$(DTAG) --file - $(DOCKER_CONTEXT) < $(DOCKERFILE)

.PHONY: run
run:
	$(DOCKER) run --rm -it --entrypoint /bin/bash $(DNAME):latest

.PHONY: tar
tar:
	$(TAR) --transform 's///' --create -T /dev/null >/dev/null 2>&1 || (echo 2>&1 "GNU tar is required: use TAR=gtar" && exit 1)
	$(GIT) ls-files  --cached --others --exclude-standard --exclude='*.tgz'| $(TAR) --transform "flags=r;s|^|dawnets_$(VERSION)/|" -czf "dawnets_$(VERSION).tgz" -T -
	echo 2>&1 "Archive written in dawnets_$(VERSION).tgz"