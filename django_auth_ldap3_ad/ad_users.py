# -*- coding: utf-8 -*-
"""
@author: Pierre-Olivier VERSCHOORE
@organization: sd-libre.fr
@contact: info@sd-libre.fr
@copyright: 2015 sd-libre.fr
@license: This file is part of Lucterios.

Lucterios is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Lucterios is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Lucterios.  If not, see <http://www.gnu.org/licenses/>.
"""
import ssl

from ldap3 import Tls

"""
scripts wildly inspired from:
https://mespotesgeek.fr/fr/python-et-utilisateurs-active-directory/
"""

from django.conf import settings
from ldap3 import Server, ServerPool, Connection, FIRST, SIMPLE, MODIFY_REPLACE
from django.core.exceptions import ImproperlyConfigured
import logging


logger = logging.getLogger(__name__)


class Aduser:
    def __init__(self):
        self.pool = None
        self.con = None
        self.connect()

    def connect(self):
        # check configuration
        if not (hasattr(settings, 'LDAP_SERVERS') and hasattr(settings, 'LDAP_BIND_ADMIN') and
                hasattr(settings, 'LDAP_BIND_ADMIN_PASS') and hasattr(settings, 'LDAP_AD_DOMAIN')
                and hasattr(settings, 'LDAP_CERT_FILE')
                ):
            raise ImproperlyConfigured()

        # first: build server pool from settings
        tls = Tls(validate=ssl.CERT_OPTIONAL, version=ssl.PROTOCOL_TLSv1, ca_certs_file=settings.LDAP_CERT_FILE)

        if self.pool is None:
            self.pool = ServerPool(None, pool_strategy=FIRST, active=True)
            for srv in settings.LDAP_SERVERS:
                # Only add servers that supports SSL, impossible to make changes without
                if srv['use_ssl']:
                    server = Server(srv['host'], srv['port'], srv['use_ssl'], tls=tls)
                    self.pool.add(server)

        # then, try to connect with user/pass from settings
        self.con = Connection(self.pool, auto_bind=True, authentication=SIMPLE,
                              user=settings.LDAP_BIND_ADMIN, password=settings.LDAP_BIND_ADMIN_PASS)

    def create_ad_user(self, user_dn, firstname, lastname, samaccountname, mail=None, description=None):
        if self.con is None:
            self.connect()

        user_attribs = {
            'objectClass': ['user'],
            'cn': "%s %s" % (firstname, lastname),
            'givenName': firstname,
            'sn': lastname,
            'displayName': '%s %s' % (firstname, lastname),
            'sAMAccountName': samaccountname,
            'userAccountControl': '514',
            'distinguishedName': user_dn,
            'userPrincipalName': "%s@%s" % (samaccountname, settings.LDAP_AD_DOMAIN)
            # 514 will set user account to disabled, 512 is enable but can't create directly
        }

        if mail is not None:
            user_attribs['mail'] = mail
        if description is not None:
            user_attribs['description'] = description

        logger.debug(self.con.add(
            user_dn,
            attributes=user_attribs
        ))
        return self.con.result

    def update_ad_user(self, user_dn, attributes):
        if self.con is None:
            self.connect()

        attribs = {}
        for attr in attributes.keys():
            attribs[attr] = [
                (MODIFY_REPLACE, [attributes[attr]])
            ]

        self.con.modify(
            user_dn,
            attribs
        )
        return self.con.result

    def activate_ad_user(self, user_dn):
        return self.update_ad_user(user_dn, {"userAccountControl": '512'})

    def update_password_ad_user(self, user_dn, newpassword):
        unicode_pass = '"%s"' % newpassword
        password_value = unicode_pass.encode("utf-16-le")

        return self.update_ad_user(user_dn, {"unicodePwd": password_value})
