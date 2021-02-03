#!/usr/bin/env python
# encoding: utf-8

"""A tool to generate changelog markdown from a git repository."""

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

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), '.version')) as fp:
    __version__ = fp.read().strip()


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
                    '\n**'+commit.subject.split('(')[0].strip()+'**\n\n' + commit.comment)

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
        lines = self.message.splitlines()
        self.subject = lines[0].strip()
        del lines[0]
        self.comment = '\n'.join(lines).strip()
        self.category, self.specific, self.description = self.categorize()

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
    def __init__(self):
        self.changes = ''

        # find repository
        self.repo = git.Repo(search_parent_directories=True)
        assert not self.repo.bare

        self.repo_name = '/'.join(self.repo.remotes.origin.url.replace(':', '/').split('.git')
                                  [0].split('/')[-2:])

        print('Collecting changelog for \'{}\'...'.format(self.repo_name))

        self.branch = 'main'
        for b in self.repo.git.branch('--contains', self.repo.head.commit.hexsha).split('\n'):
            b = b.replace('*', '').replace(' ', '')
            if b.startswith('('):
                continue
            if b.startswith('HEAD'):
                continue
            self.branch = b
            break
        # branch = repo.git.rev_parse('--abbrev-ref', 'HEAD')
        print('Branch: {}'.format(self.branch))
        self.commit = self.repo.git.rev_parse('HEAD')
        print('Commit: {}'.format(self.commit))

        self.date = datetime.datetime.fromtimestamp(
            self.repo.head.commit.committed_date)
        print('Date: {}'.format(self.date))

        # find current version
        self.version = '.'.join(
            self.repo.git.describe('--always', '--tags', '--match=v*.*')
                .strip()
                .replace('-', '.')
                .split('.')[:3]
        ).strip()
        assert len(self.version) > 0
        print('Version: {}'.format(self.version))

    def update_changes(self, from_ref, do_comments=True, releases_repo_name=None):

        if not releases_repo_name:
            releases_repo_name = self.repo_name
        self.releases_repo_name = releases_repo_name

        self.from_ref = from_ref

        self.from_hexsha = self.repo.git.rev_parse(from_ref)

        self.changes = ''
        try:
            commits = list(self.repo.iter_commits(from_ref + ".."))
        except git.exc.GitCommandError:
            commits = list(self.repo.iter_commits())
            self.from_ref = 'initial commit ({})'.format(commits[0])

        commits = list(map(Commit, commits))  # Convert to Commit objects
        commits = sorted(commits, key=lambda c: c.date)
        commits = list(filter(lambda c: c.category, commits))
        commits = Commits(commits)

        # Set up the templating engine
        template_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'templates')
        loader = FileSystemLoader(template_dir)
        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        template = env.get_template('changes.jinja2')

        if do_comments:
            comments = commits.comments
        else:
            comments = None

        changelog = template.render(
            commits=commits,
            comments=comments
        ).strip().replace('\r', '')

        while '\n\n\n' in changelog:
            changelog = changelog.replace('\n\n\n', '\n\n')

        changes = changelog.strip()
        if len(changes) == 0:
            changes = 'Security updates'

        # fix embedded links to issues
        # explicitly referenced repo
        p = re.compile(r'([a-z+-]+\/[a-z-]+)\#([0-9-]+)')
        changes = p.sub(
            r'[`\2`](https://github.com/\1/issues/\2)', changes)

        # no referenced repo
        p = re.compile(r'\#([0-9-]+)')
        changes = p.sub(
            r'[`\1`](https://github.com/{}/issues/\1)'.format(self.releases_repo_name), changes)

        self.changes = changes

    def update_log(self, changelog_file, title=None, releases_repo_name=None):
        if not releases_repo_name:
            releases_repo_name = self.repo_name
        if not title:
            title = 'Release'

        changelog_entry_title = '# [{0} {1}](https://github.com/{2}/releases/tag/{3}) ({4})'.format(
            title, self.version, releases_repo_name, self.version.replace('v', 'release-'), self.date.strftime('%x'))

        changelog_entry_header = '> Branch: `{0}`'.format(
            self.branch)

        changelog_entry_header += '\\\n> Date: `{0}`'.format(
            self.date.strftime('%x %X'))

        if self.from_hexsha:
            changelog_entry_header += '\\\n> Diff: [{0}](https://github.com/{0}/compare/{1}...{2})'.format(
                self.repo_name, self.from_hexsha, self.repo.head.commit.hexsha)

        # update changelog file
        tmpl = None
        tmpl_file = os.path.join(
            self.repo.working_tree_dir, '.changelog')
        if os.path.exists(tmpl_file):
            with open(tmpl_file, 'r') as f:
                tmpl = f.read().strip()

        changelog_tmp = changelog_file + '.tmp'

        with open(changelog_tmp, 'w') as tmp:
            content = changelog_entry_title + '\n\n'
            content += changelog_entry_header + '\n\n'
            content += re.sub(r'^#', '##', self.changes, flags=re.M) + '\n\n'

            if tmpl:
                tmp.write(tmpl + '\n\n')
                content = re.sub(r'^#', '##', content, flags=re.M)
                hdr = '## '
                changelog_entry_title = '#'+changelog_entry_title
            else:
                hdr = '# '

            tmp.write(content)

            # append tail from old
            if os.path.exists(changelog_file):
                with open(changelog_file, 'r') as old:
                    ok = False
                    for line in old:
                        if not ok and line.startswith(hdr) and not line.startswith(changelog_entry_title):
                            ok = True
                        if not ok:
                            continue
                        tmp.write(line)
                    old.close()
            tmp.close()
            if os.path.exists(changelog_file):
                os.unlink(changelog_file)
            os.rename(changelog_tmp, changelog_file)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Changelog generator for git repository')
    parser.add_argument('--ref', action='store', required=True,
                        help='git ref from which to collect changes')
    parser.add_argument('--comments', action='store_true', default=True,
                        help='append comments section')
    parser.add_argument('--out', action='store',
                        help='output filename to store collected changelog markdown text')
    parser.add_argument('--releases', action='store',
                        help='releases repository name if different')
    parser.add_argument('--log', action='store',
                        help='filename of changelog file to update')
    parser.add_argument('--title', action='store',
                        help='project title for changelog file updates')
    parser.add_argument('--ver', action='store',
                        help='project version X.Y[.Z] for changelog file updates')
    parser.add_argument('--mkver', action='store',
                        help='filename to store current version (X.Y.Z)')
    args = parser.parse_args()

    ch = Changelog()

    if args.ver:
        ch.version = 'v'+args.ver

    if args.ref:
        ch.update_changes(args.ref, args.comments, args.releases)

    if args.out:
        with open(args.out, 'w') as f:
            f.write(ch.changes)
            f.write('\n')
    else:
        print('Changes since {}:\n----\n{}\n----'.format(ch.from_ref, ch.changes))

    if args.log:
        print('Updating changelog: {}'.format(args.log))
        ch.update_log(args.log, args.title, args.releases)

    if args.mkver:
        with open(args.mkver, 'w') as f:
            f.write(ch.version.replace('v', ''))

    return 0


if __name__ == "__main__":
    sys.exit(main())
