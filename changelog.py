#!/usr/bin/env python
# encoding: utf-8

"""A tool to generate changelogfrom a git repository."""

# Copyright (c) 2021 Aliaksei Stratsilatau
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import argparse

import datetime
import os
import sys
import re
from collections import defaultdict

import git
from jinja2 import Environment, FileSystemLoader

__version__ = '0.0.1'
__author__ = 'Aliaksei Stratsilatau'
__license__ = 'MIT'


class Commits:
    def __init__(self, commits):
        self.name = 'Unreleased'
        self.groups = defaultdict(list)
        self.commits = commits

        self.comments = list()

        for commit in commits:
            self.add_commit(commit)
            if len(commit.comment) > 0:
                self.comments.append(
                    '**'+commit.subject.split('(')[0].strip()+'**\n\n' + commit.comment)

    def add_commit(self, commit):
        self.groups[commit.category].append(commit)

    def __repr__(self):
        return '<{}: {!r}>'.format(
            self.__class__.__name__,
            self.name)


class Commit:
    def __init__(self, commit):
        self._commit = commit
        self.date = datetime.datetime.fromtimestamp(commit.committed_date)
        self.commit_hash = commit.hexsha
        self.message = commit.message.strip()
        lines = self.fix_links(self.message).splitlines()
        self.subject = lines[0].strip()
        del lines[0]
        self.comment = '\n'.join(lines).strip()
        self.category, self.specific, self.description = self.categorize()

    def fix_links(self, str):
        # fix embedded links to issues
        p = re.compile(r'([a-z+-]+\/[a-z-]+)\#([0-9-]+)')
        fixed = p.sub(r'[`issue \2`](http://github.com/\1/issues/\2)', str)
        return fixed

    def categorize(self):
        match = re.match(r'(\w+)(\(\w+\))?:\s*(.*)', self.subject)

        if match:
            category, specific, description = match.groups()
            # Remove surrounding brackets
            specific = specific[1:-1] if specific else None
            return category, specific, description
        else:
            return None, None, None

    def __repr__(self):
        return '<{}: {} "{}">'.format(
            self.__class__.__name__,
            self.commit_hash[:7],
            self.date.strftime('%x %X'))


class Changelog:
    def __init__(self, remote, token):
        # find repository
        if remote:
            self.remote = remote
        else:
            self.remote = 'uavos/apx-releases'

        self.repo = git.Repo(search_parent_directories=True)
        assert not self.repo.bare
        print('Deploying project \'' +
              self.repo.working_tree_dir.split('/')[-1] + '\'...')

        self.branch = 'master'
        for b in self.repo.git.branch('--contains', self.repo.head.commit.hexsha).split('\n'):
            b = b.replace('*', '').replace(' ', '')
            if b.startswith('('):
                continue
            if b.startswith('HEAD'):
                continue
            self.branch = b
            break
        # branch = repo.git.rev_parse('--abbrev-ref', 'HEAD')
        print('Branch: ' + self.branch)
        self.commit = self.repo.git.rev_parse('HEAD')
        print('Commit: ' + self.commit)

        self.date = datetime.datetime.fromtimestamp(
            self.repo.head.commit.committed_date)
        print('Date: ' + self.date.strftime('%x %X'))

        # find current version
        self.version = '.'.join(
            self.repo.git.describe('--always', '--tags', '--match=v*.*')
                .strip()
                .replace('v', '')
                .replace('-', '.')
                .split('.')[0:3]
        ).strip()
        assert len(self.version) > 0
        print('Version: ' + self.version)

        # find deploy repo
        remote_name = os.path.split(self.remote)[1]
        deploy_repo_dir = os.path.join(
            self.repo.working_tree_dir, '..', remote_name)
        if not os.path.exists(deploy_repo_dir):
            print('Clone \'{}\'...'.format(remote_name))
            self.deploy_repo = git.Repo.clone_from(
                'https://{0}@github.com/{1}.git'.format(token, self.remote), deploy_repo_dir)
        else:
            print('Pull \'{}\'...'.format(remote_name))
            self.deploy_repo = git.Repo(deploy_repo_dir)
            # self.deploy_repo.remotes.origin.pull()

        # find published version
        version_pub = self.deploy_repo.git.describe(
            '--abbrev=0', '--tags', '--always', '--match=*.*')
        print('Latest published version: ' + version_pub)

        self.changes = None
        self.published = False

    def update(self):
        if self.changes:
            return
        # check if already published
        self.published = False
        prev_ref = ''
        try:
            tag_apx = self.deploy_repo.tags['apx']
            prev_ref = tag_apx.tag.message.strip().split('\n')[0]
            print('Latest published commit: ' + prev_ref)
            if prev_ref == self.commit:
                print('ALREADY DEPLOYED')
                self.published = True
        except IndexError:
            print('Clean releases repository')

        # release notes file
        notes_path = os.path.join(self.deploy_repo.working_tree_dir, 'notes')
        if not os.path.exists(notes_path):
            os.makedirs(notes_path)
        notes_file = os.path.join(
            notes_path, 'release-{}.md'.format(self.version))
        if not self.published:
            self.changes = self.update_changes(prev_ref)
            self.changes = re.sub(r'^#', '####', self.changes, flags=re.M)
            with open(notes_file, 'w') as f:
                f.write(self.changes)
                f.close()
            self.deploy_repo.index.add([notes_file])
        else:
            with open(notes_file, 'r') as f:
                self.changes = f.read()
                f.close()

    def update_changes(self, prev_ref):
        changes = ''
        if prev_ref != '':
            changes = self.get_changelog(prev_ref, do_comments=True)

        if len(changes) == 0:
            changes = 'Security updates and latest firmware `{}`'.format(
                self.date.strftime('%x'))

        changelog_file = os.path.join(
            self.deploy_repo.working_tree_dir, 'CHANGELOG.md')
        changelog_tmp = changelog_file + '.tmp'

        changelog_entry_title = \
            '## [Version ' + self.version + '](https://github.com/{}/releases/tag/'.format(self.remote) + self.version + ')' \
            + ' (' + self.date.strftime('%x') + ')'

        changelog_entry_header = \
            '> Branch: `' + self.branch + '`' \
            + '  \nDate: `' + self.date.strftime('%x %X') + '`'
        if prev_ref != '':
            changelog_entry_header += \
                '  \nDiff: [uavos/apx](https://github.com/uavos/apx/compare/' + \
                prev_ref + '...' + self.repo.head.commit.hexsha + ')'

        # check for dirty run
        if os.path.exists(changelog_tmp) and not os.path.exists(changelog_file):
            os.rename(changelog_tmp, changelog_file)

        with open(changelog_tmp, 'w') as tmp:
            tmp.write('# Changelog\n\n'
                      'All notable changes to **APX Software** will be documented in this file.  \n'
                      'For more information refer to [docs.uavos.com](http://docs.uavos.com).\n\n')
            tmp.write(changelog_entry_title + '\n\n')
            tmp.write(changelog_entry_header + '\n\n')
            tmp.write(re.sub(r'^#', '###', changes, flags=re.M) + '\n\n')
            # append tail from old
            if os.path.exists(changelog_file):
                with open(changelog_file, 'r') as old:
                    ok = False
                    for line in old:
                        if line.startswith('## ') and not line.startswith(changelog_entry_title):
                            ok = True
                        if not ok:
                            continue
                        tmp.write(line)
                    old.close()
            tmp.close()
            if os.path.exists(changelog_file):
                os.unlink(changelog_file)
            os.rename(changelog_tmp, changelog_file)

        self.deploy_repo.index.add([changelog_file])
        return changes

    def get_changelog(self, from_ref, title=None, do_comments=False):
        commits = list(self.repo.iter_commits(from_ref + ".."))
        commits = list(map(Commit, commits))  # Convert to Commit objects
        commits = sorted(commits, key=lambda c: c.date)
        commits = list(filter(lambda c: c.category, commits))
        commits = Commits(commits)

        # Set up the templating engine
        template_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'templates'),
        loader = FileSystemLoader(template_dir)
        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        template = env.get_template('changes.jinja2')

        if do_comments:
            comments = commits.comments
        else:
            comments = None

        changelog = template.render(
            title=title,
            commits=commits,
            comments=comments
        ).strip().replace('\r', '')

        while '\n\n\n' in changelog:
            changelog = changelog.replace('\n\n\n', '\n\n')

        return changelog

    def publish(self):
        deploy_msg = 'Update to version ' + self.version
        if len(self.deploy_repo.index.diff('HEAD')) > 0:
            print('New commit to deploy repo: ' + deploy_msg)
            self.deploy_repo.git.commit('-a', '-S', '-m', deploy_msg)
        else:
            print('Deploy repo already committed (' +
                  self.deploy_repo.head.commit.message.strip() + ')')
            assert self.deploy_repo.head.commit.message.strip() == deploy_msg

        # create tags
        self.deploy_repo.create_tag(
            '-s', self.version, force=True, message=deploy_msg)
        self.deploy_repo.create_tag('apx', force=True, message=self.commit)

        # Push deploy to git
        if sum(1 for c in self.deploy_repo.iter_commits('origin/HEAD..HEAD')) > 0:
            print('Pushing deploy tags to git...')
            self.deploy_repo.remotes.origin.push(['-f', '--tags'])
            print('Pushing deploy commits to git...')
            self.deploy_repo.remotes.origin.push()
        else:
            print('Deploy repo already pushed')


def main():
    """Main function."""
    return 0


if __name__ == "__main__":
    sys.exit(main())
