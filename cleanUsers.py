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

import sys
import string
import random
import logging

# SEARCHSIZE is how many we should ask for in each search
SEARCHSIZE=1000
# BATCHSIZE is the number of deletes we should do in a SCIM BULK call
BATCHSIZE=100

# logging.basicConfig(filename='myapp.log', level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(levelname)7s %(module)s:%(funcName)s -> %(message)s', level=logging.INFO)
logging.debug("Starting up")


from IAMClient import IAMClient
iam = IAMClient()

# We need the App ID of the application defined in the config file
# this allows us to delete only the users created by the fakeUsers.py script
myAppID = iam.GetMyAppID()

# this is the last "ID" number we saw.
# see my blog post for why I do this!
lastId = 0

# start with an empty array
reqs = []

# I like while loops for some reason
cont = True
while cont:
        # this filter uses the app ID we looked up above
        # and the last user "id" we saw
        # we do the latter b/c of an oddity of SCIM (see my blog post and the RFC)
        # https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.2.4
        filter = 'idcsCreatedBy.value eq "{}" and id gt "{}"'.format(myAppID,lastId)
        logging.debug( "Filter: {}".format( filter ))
        # my search options
        args =  {
                "sortBy": "id",
                "attributes": "id",
                "filter": filter,
                "count": SEARCHSIZE
                }

        try:
                users = iam.GetUsers(args)

                for user in users:
                        logging.info("User {} -> {}".format( user["id"], user["userName"]) )
                        lastId = user["id"]
                        # create a DELETE request for the user id (note: not username - this is the value of the id attribute of the user object)
                        reqs += [{
                                        "method": "DELETE",
                                        "path": "/Users/" + user["id"],
                                        "bulkId": ''.join(random.choices(string.ascii_lowercase,k=10)),
                                }]

                        if BATCHSIZE == len( reqs ):
                                logging.info("Deleting {} users".format(len(reqs)))
                                iam.bulkRequest(reqs)
                                logging.info("Done.")
                                reqs = []

        except IAMClient.Error:
                # when we run out of users to delete we're done
                cont = False

logging.info("Deleting last {} users".format(len(reqs)))
iam.bulkRequest(reqs)
logging.info("Done.")
