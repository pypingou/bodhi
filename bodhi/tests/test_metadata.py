# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import os
import shutil
import tempfile
import turbogears

from pprint import pprint
from os.path import join, isfile
from turbogears import testutil, database
from bodhi.util import mkmetadatadir
from bodhi.model import Release, Package, PackageUpdate, Bugzilla, CVE, Arch
from bodhi.metadata import ExtendedMetadata

import sys
sys.path.append('/home/lmacken/code/cvs.duke/yum/yum/')
from update_md import UpdateMetadata
#from yum.update_md import UpdateMetadata

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')

class TestExtendedMetadata(testutil.DBTest):

    def test_metadata(self):
        """
        Test the creation of a PackageUpdate, and the generation of extended
        metadata for the update.
        """
        ## Create an update
        pkg = Package(name='foobar')
        arch = Arch(name='i386', subarches=['i386'])
        rel = Release(name='fc7', long_name='Fedora Core 7', repodir='7')
        rel.addArch(arch)
        up = PackageUpdate(nvr='mutt-1.4.2.2-4.fc7', package=pkg, release=rel,
                           submitter='foo@bar.com', testing=True,
                           type='security', notes='Update notes and such')
        bug = Bugzilla(bz_id=1234)
        cve = CVE(cve_id="CVE-2006-1234")
        up.addBugzilla(bug)
        up.addCVE(cve)
        up._build_filelist()
        up.assign_id()

        ## Initialize our temporary repo
        push_stage = tempfile.mkdtemp('bodhi')
        for arch in up.release.arches:
            mkmetadatadir(join(push_stage, up.get_repo(), arch.name))

        ## Add update and insert updateinfo.xml.gz into repo
        md = ExtendedMetadata(stage=push_stage)
        md.add_update(up)
        md.insert_updateinfo()

        ## Make sure the updateinfo.xml.gz actually exists
        updateinfo = join(push_stage, up.get_repo(), 'i386',
                          'repodata', 'updateinfo.xml.gz')
        assert isfile(updateinfo)

        ## Attempt to read the metadata
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice('mutt-1.4.2.2-4.fc7')

        assert notice['description'] == up.notes
        assert notice['update_id'] == up.update_id
        assert notice['status'] == 'testing'
        assert notice['from'] == 'updates@fedora.redhat.com'
        assert notice['type'] == up.type

        ## Verify file list
        files = []
        map(lambda x: map(lambda y: files.append(y.split('/')[-1]), x),
                          up.filelist.values())
        for pkg in notice['pkglist'][0]['packages']:
            assert pkg['filename'] in files

        del uinfo
        assert md.remove_update(up)
        md.insert_updateinfo()
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice('mutt-1.4.2.2-4.fc7')
        assert not notice

        ## Clean up
        shutil.rmtree(push_stage)
