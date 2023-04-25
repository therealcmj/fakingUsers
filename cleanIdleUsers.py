#!/usr/bin/env python3


################################################################################
# Copyright (c) 2022-2023, Oracle and/or its affiliates.  All rights reserved.
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

# this is for our worker thread pool
import concurrent.futures
futures = []
# and this actually creates the thread pool that we will use to do the deletes asynchronously
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# SEARCHSIZE is how many we should ask for in each search
SEARCHSIZE=100
# BATCHSIZE is the number of deletes we should do in a SCIM BULK call
BATCHSIZE=20

# how do you define an "idle" user
# in this case I do it by how many days since the last time they logged in
DAYSIDLE=90

# logging.basicConfig(filename='myapp.log', level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(levelname)7s %(module)s:%(funcName)s -> %(message)s', level=logging.DEBUG)
logging.debug("Starting up")


from IAMClient import IAMClient
iam = IAMClient()

# calculate now minus DAYSIDLE
from datetime import datetime, timedelta
logging.debug("Current time: {}".format(datetime.now().strftime("%c")))
deletedatetime = datetime.utcnow() + timedelta(days=-DAYSIDLE)
logging.info("will delete users who have not logged in since {}".format(deletedatetime.strftime("%c")))

# reformat it to look like this:
# 2022-02-18T22:21:24.780Z
deletedatetime = deletedatetime.isoformat(sep='T',timespec='seconds') + "Z"
logging.debug("Timestamp for search {}".format(deletedatetime))

# this is the last "ID" number we saw.
# see my blog post for why I do this!
lastId = 0

# start with an empty array
reqs = []

# I like while loops for some reason
cont = True
while cont:
        # this filter uses the time string we built above (some number of days ago)
        # and the last user "id" we saw
        # we do the latter b/c of an oddity of SCIM (see my blog post and the RFC)
        # https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.2.4
        logging.debug("Constructing search filter...")
        filter = 'urn:ietf:params:scim:schemas:oracle:idcs:extension:userState:User:lastSuccessfulLoginDate lt "{}" and id gt "{}"'.format(deletedatetime,lastId)
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
                                        "path": "/Users/" + user["id"] + "?forceDelete=true",
                                        "bulkId": ''.join(random.choices(string.ascii_lowercase,k=10)),
                                }]

                        if BATCHSIZE == len( reqs ):
                                logging.info("Queuing {} users for deletion".format(len(reqs)))
                                futures.append(executor.submit(iam.bulkRequest, reqs))
                                logging.info("Queued.")
                                reqs = []

        except IAMClient.Error:
                # when we run out of users to delete we're done
                cont = False

logging.info("Queuing last {} users for deletion".format(len(reqs)))
futures.append(executor.submit(iam.bulkRequest, reqs))
logging.info("Queued.")

logging.info("Waiting for worker pool to complete.")
for future in concurrent.futures.as_completed(futures):
        if future.done():
                logging.info("Future is done")
        elif future.cancelled():
                logging.info("Future is cancelled")
        # this shouldn't happen but just in case
        else:
                logging.error("Future did something weird")
        # print(future.result())
