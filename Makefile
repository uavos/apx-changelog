GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)


all: clean build

build:
	@python setup.py sdist bdist_wheel

clean:
	@rm -Rf build dist *.egg-info

install:
	@pip install dist/*.whl

uninstall:
	@pip install apx-changelog

release: update-changelog
	@echo "Requesting release..."
	@git add -A
	@git commit -a -m "Release $(shell cat .version)" || echo "Nothing to commit"
	@git tag -f release-$(shell cat .version)
	@git tag -f changelog
	@git push
	@git push --tags
	@git fetch . $(GIT_BRANCH):release -f
	@git push origin release -f

update-changelog:
	@echo "Updating changelog..."
	@./apxchangelog.py --ref 'changelog' --log CHANGELOG.md --mkver .version

