#!/usr/bin/env python3

################################################################################
# Copyright (c) 2022, Oracle and/or its affiliates.  All rights reserved.
# This software is dual-licensed to you under the Universal Permissive License
# (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl or Apache License
# 2.0 as shown at http://www.apache.org/licenses/LICENSE-2.0. You may choose 
# either license.

# This code is provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND.
# It is intended for single purpose and should be discarded after use.
################################################################################

import string
import random
import logging

# this script doesn't check your work
# so make sure that NUMUSERS is divisible by BATCHSIZE please
NUMUSERS=1000
BATCHSIZE=100

logging.basicConfig(format='%(asctime)s %(levelname)7s %(module)s:%(funcName)s -> %(message)s', level=logging.DEBUG)
logging.debug("Starting up")

from faker import Faker
fake = Faker()

from IAMClient import IAMClient
idcs = IAMClient()

for iRequests in range( int( NUMUSERS / BATCHSIZE ) ):
    reqs = []
    for iUsers in range(BATCHSIZE):

        gn = fake.first_name()
        sn = fake.last_name()
        email = fake.email()

        reqs += [{
                "method": "POST",
                "path": "/Users/",
                "bulkId": ''.join(random.choices(string.ascii_lowercase,k=10)),
                "data": {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "name": {
                        "givenName": gn,
                        "familyName": sn,
                        "formatted": gn + " " + sn,
                    },
                    # "userName": ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)),
                    "userName": email,
                    "emails": [
                        {
                            "value": email,
                            "type": "work",
                            "primary": True
                        }
                    ],
                    "urn:ietf:params:scim:schemas:oracle:idcs:extension:user:User:bypassNotification": True
                }
            }]

    logging.info("Generated {} users".format(iUsers+1))
    logging.info("Sending request {}.".format(iRequests+1))
    idcs.bulkRequest(reqs)
