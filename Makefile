GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)


all: clean build

build:
	@python3 setup.py sdist bdist_wheel

clean:
	@rm -Rf build dist *.egg-info

install:
	@pip3 install dist/*.whl

uninstall:
	@pip3 uninstall -y apx-changelog

release: update-changelog
	@echo "Requesting release..."
	@git add -A
	@git commit --amend --no-edit
	@git tag -f release-$(shell cat .version)
	@git tag -f changelog
	@git push -f
	@git push -f --tags
	@git fetch . $(GIT_BRANCH):release -f
	@git push origin release -f

update-changelog:
	@echo "Updating changelog..."
	@if git diff-index --quiet HEAD --; then echo "No changes"; else echo "Uncommitted changes" && exit 1; fi
	@python3 apxchangelog.py --ref 'changelog' --log CHANGELOG.md --mkver .version

