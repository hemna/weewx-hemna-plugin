"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                        Installer for GW1000 Driver

Version: 0.1.0                                        Date: 14 October 2021

Revision History
    1 September 2020    v0.1.0 (b1-b12)
        -   initial implementation
"""

# python imports
import configobj
from distutils.version import StrictVersion
import setup

# import StringIO, use six.moves due to python2/python3 differences
from six.moves import StringIO

# WeeWX imports
import weewx


REQUIRED_VERSION = "3.7.0"
HEMNA_VERSION = "0.1.0"
# define our config as a multiline string so we can preserve comments
hemna_config = """
"""

# construct our config dict
# hemna_dict = configobj.ConfigObj(StringIO(hemna_config))

hemna_dict = {
    'StdRESTful': {
        'Hemna': {
            'server_url': 'www.hemna.com',
            'station': 'nothing',
            'enable': 'true',
            'password': 'password'
        }
    }
}


def loader():
    return HemnaInstaller()


class HemnaInstaller(setup.ExtensionInstaller):
    def __init__(self):
        if StrictVersion(weewx.__version__) < StrictVersion(REQUIRED_VERSION):
            msg = "%s requires WeeWX %s or greater, found %s" % (''.join(('Hemna driver ', HEMNA_VERSION)),
                                                                 REQUIRED_VERSION,
                                                                 weewx.__version__)
            raise weewx.UnsupportedFeature(msg)
        super(HemnaInstaller, self).__init__(
            version=HEMNA_VERSION,
            name='Hemna',
            description='Hemna wx.hemna.com service',
            author="Walter A. Boring IV",
            author_email="waboring@hemna.com",
            restful_services='user.hemna.StdHemna',
            files=[('bin/user', ['bin/user/hemna.py'])],
            config=hemna_dict
        )
