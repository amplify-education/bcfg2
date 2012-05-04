import os
import re
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.Properties')

class Fake(object):
    """
    An object that pretends to be an lxml etree node, but that has no children, fake text, and
    that duplicates itself when any attribute is retrieved or when it is called
    """
    def __init__(self, name):
        self.name = name

    def __getattr__(self, name):
        if name == 'text':
            return str(self)
        else:
            return Fake('.'.join([self.name, name]))

    def __call__(self, *args, **kwargs):
        return Fake('%s(args=%s, kwargs=%s)' % (self.name, args, kwargs))

    def __str__(self):
        return "FAKE: " + self.name

    def __iter__(self):
        if False:
            yield None
        return

    def __getitem__(self, key):
        return Fake('%s[%s]' % (self.name, key))

    def __len__(self):
        return 0

class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
    def write(self):
        """ Write the data in this data structure back to the property
        file """
        if self.validate_data():
            try:
                open(self.name,
                     "wb").write(lxml.etree.tostring(self.xdata,
                                                     pretty_print=True))
                return True
            except IOError:
                err = sys.exc_info()[1]
                logger.error("Failed to write %s: %s" % (self.name, err))
                return False
        else:
            return False

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for this property file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except:
                logger.error("Failed to process schema for %s" % self.name)
                return False
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            logger.error("Data for %s fails to validate; run bcfg2-lint for "
                         "more details" % self.name)
            return False
        else:
            return True


class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile
    patterns = re.compile(r'.*\.xml$')


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            self.logger.error("Error while creating Properties store: %s %s" %
                              (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError

        opts = dict(configfile=Bcfg2.Options.CFILE,
                    default_props=Bcfg2.Options.Option(
                "Property files to mock out if they don't exist",
                cmd="--default-property-files", default=[], long_arg=True,
                cf=('testing', 'default_property_files'),
                env="DEFAULT_PROPERTY_FILES", cook=Bcfg2.Options.colon_split))
        setup = Bcfg2.Options.OptionParser(opts)
        setup.parse(sys.argv[1:], False)

        self.default_property_files = setup['default_props']

    def get_additional_data(self, _):
        props = copy.copy(self.store.entries)
        for fname in self.default_property_files:
            if fname not in props.keys():
                props[fname] = Fake(fname)
        return props
