
################################################################################
# Copyright (c) 2022, Oracle and/or its affiliates.  All rights reserved.
# This software is dual-licensed to you under the Universal Permissive License
# (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl or Apache License
# 2.0 as shown at http://www.apache.org/licenses/LICENSE-2.0. You may choose 
# either license.

# This code is provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND.
# It is intended as a demonstration and should not be used for any other purposes.

#
# Note: This code is a very dumb and is intended as a simple example of how to
# make SCIM calls. It has little to no sanity checking and will throw whatever
# exceptions the underlying layer throws when it encounters a problem
#
# The big exception to the above is in the bulk call.
# Which is somehow even worse. Specifically it doesn't bother to tell you if
# any of the requests inside the bulk request failed. It just happily continues
#
# You have been warned!
# 
################################################################################

import json
import logging

# OAuth stuff
import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
import urllib.parse

# # debug HTTP
# import http.client as http_client
# http_client.HTTPConnection.debuglevel = 2

class IAMClient:
    class Error(Exception):
        """Base class for other exceptions"""
        pass

    class NoResults(Error):
        """Raised when the search returns no results"""
        pass

    idcsUrl = None
    clientID = None
    clientSecret = None

    oauthClient = None

    def __init__(self):
        # load the config from the json file
        config = json.load(open('IAMClientConfig.json'))

        # this code looks a little funny b/c I copy/pasted stuff from old code and am lazy
        # please forgive me :-)
        idcsURL      = config["iamurl"]
        clientID     = config["client_id"]
        clientSecret = config["client_secret"]

        # TODO: add checks

        logging.info("Initializing IDCS client with the following params:")
        logging.info("IAM URL: {}".format(idcsURL))
        logging.info("Client ID: {}".format(clientID))
        logging.info("Client Secret: {}".format(clientSecret))

        self.idcsUrl = idcsURL
        # save these just in case
        self.clientID = clientID
        self.clientSecret = clientSecret

        auth = HTTPBasicAuth(clientID, clientSecret)
        client = BackendApplicationClient(client_id=clientID)
        self.oauthClient = OAuth2Session(client=client)

        # NOTE: we don't actually need the access token ourselves
        #       The requests_oauthlib handles calling oauthlib to acquire that
        #       when it's needed. And as a bonus it also gets a new one if that
        #       expires.
        #
        # BUT: I go and get one here so that I know if the config settings are right
        #      before the other code tries to use the library for something.
        #
        # If acquiring the AT fails this code will throw an exception.
        token = self.oauthClient.fetch_token(   token_url=idcsURL + '/oauth2/v1/token',
                                                auth=auth,
                                                scope=["urn:opc:idm:__myscopes__"])
        logging.debug( "Access Token: {}".format(token.get("access_token")))
        return

    def GetUsers(self, params):
        logging.debug("GetUsers() called")

        uri = "/admin/v1/Users"
        if params:
            uri += "?" + urllib.parse.urlencode( params )
        results = self._sendRequest( "GET", uri, None )

        if results["totalResults"] == 0:
            raise IAMClient.NoResults( "Zero results" )
        return results["Resources"]

        # logging.debug("Status code: {}".format(response.status_code))
        # if response.ok:
        #     logging.debug( "Response indicates success" )
        #     # TODO: something!
            
        # else:
        #     logging.debug( "Error!" )

    def GetApps(self, params):
        logging.debug("GetApps() called")
        
        uri = "/admin/v1/Apps"
        if params:
            uri += "?" + urllib.parse.urlencode( params )
        return self._sendRequest( "GET", uri, None )
        # response = self.oauthClient.get(self.idcsUrl + "/admin/v1/Apps")
        # print("Status code: {}".format(response.status_code))
        # if response.ok:
        #     print( "Response indicates success" )
        #     # TODO: something!
        # else:
        #     print( "Error!" )


    def GetMyAppID(self):
        logging.debug("GetMyAppID() called")
        result = self.GetApps( {
                                "filter" : "name eq \"" + self.clientID + "\"",
                                "attributes" : "id"
                               })
        id = result["Resources"][0]["id"]
        logging.info( "Got ID for app as {}".format(id) )
        return id

    def CreateApp(self, clientName, redirectUris):
        logging.debug("CreateApp() called")
        appPayload = {
            "displayName": clientName,
            "redirectUris": redirectUris,

            # the rest of these are more or less "fixed" values needed for an OAuth app
            "allUrlSchemesAllowed": True,
            "description": "created via DCR PoC code",
            "clientType": "confidential",
            "allowedGrants": [
                "authorization_code"
            ],
            "isOAuthClient": True,
            "basedOnTemplate": {
                "value": "CustomWebAppTemplateId"
            },
            "schemas": [
                "urn:ietf:params:scim:schemas:oracle:idcs:App"
            ]
        }

        createResponse = self._sendRequest( "POST", "/admin/v1/Apps", appPayload )

        logging.debug("Getting id from response")
        id = createResponse.get("id")
        if not id:
            logging.debug("ID not present in response!")
            raise Exception("Failed to get ID for newly created app!" )

        logging.debug("Activating newly created app with id {}".format(id))
        self.SetAppActiveStatus( id, True)

        # The caller needs the client ID + secret
        logging.debug("Returning client ID + client secret")
        return (createResponse.get("name"), createResponse.get("clientSecret"))

    def SetAppActiveStatus(self, id, status):
        appActivatePayload = {"active": status, "schemas": ["urn:ietf:params:scim:schemas:oracle:idcs:AppStatusChanger"]}
        activateResponse = self._sendRequest( "PUT", "/admin/v1/AppStatusChanger/" + id, appActivatePayload )

    def DeleteApp(self, id):
        logging.debug("Deleting app with ID {}".format(id))
        # in order to delete an app you need to be sure it's deactivated
        self.SetAppActiveStatus(id,False)
        self._sendRequest( "DELETE", "/admin/v1/Apps/" + id, None)
        return

    def DeleteAppWithClientID(self, clientID):
        # IDCS will not allow more than one app to have the same "name"
        # so this will return either 0 or 1 results.
        response = self._sendRequest("GET",
                                     "/admin/v1/Apps?filter=name+eq+%22" + clientID + "%22",
                                     None)

        if response and 1 == response.get("totalResults"):
            #response.get("name") and response.get("id"):
            #return self.DeleteApp(response.get("id"))
            id = response.get("Resources")[0].get("id")
            logging.debug( "Found app to delete - IDCS id is {}".format(id))
            self.DeleteApp(id)
        else:
            logging.error("Could not find app to delete!")
            raise Exception("Unable to find app to delete")

        return

    def getGroupId(self, displayName):
        response = self._sendRequest("GET",
                                     "/admin/v1/Groups?filter=displayName+eq+%22" + urllib.parse.quote(displayName) + "%22",
                                     None)
        if response and 1 == response.get("totalResults"):
            id = response.get("Resources")[0].get("id")
            logging.debug( "Returning ID {}".format(id))
            return id
        else:
            raise Exception("Failed to get ID for group!" )

    def getAppRoleID(self, appRole):
        response = self._sendRequest("GET",
                                     "/admin/v1/AppRoles?filter=displayName+eq+%22" + urllib.parse.quote(appRole) + "%22",
                                     None)
        if response and 1 == response.get("totalResults"):
            id = response.get("Resources")[0].get("id")
            logging.debug( "Returning ID {}".format(id))
            return id
        else:
            raise Exception("Failed to get ID for AppRole!" )

    def grantAppRoleToGroup(self, appRoleName, groupName):

        grant_payload = {
            "grantee": {
                "type": "Group",
                "value": "" + self.getGroupId(groupName) + ""
            },
            "app": {
                "value": "IDCSAppId"
            },
            "entitlement": {
                "attributeName": "appRoles",
                "attributeValue": "" + self.getAppRoleID(appRoleName) + ""
            },
            "grantMechanism": "ADMINISTRATOR_TO_GROUP",
            "schemas": [
                "urn:ietf:params:scim:schemas:oracle:idcs:Grant"
            ]
        }

        self._sendRequest("POST", "/admin/v1/Grants", grant_payload)

    def bulkRequest(self, reqs):
        bulkReq = {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
                    "Operations" :
                        []
        }

        bulkReq["Operations"] += reqs
        self._sendRequest("POST", "/admin/v1/Bulk", bulkReq)



    def _sendRequest(self, verb, uri, jsonpayload):
        if verb == "POST":
            logging.debug("Sending POST payload:")
            logging.debug(json.dumps(jsonpayload))

        # response = self.oauthClient.post(self.idcsUrl + uri,
        response = self.oauthClient.request(verb, self.idcsUrl + uri,
                                     json = jsonpayload,
                                     headers = {
                                         "Content-Type":"application/scim+json",
                                         "Accept":"application/scim+json,application/json"
                                     })

        logging.debug("Status code: {}".format(response.status_code))
        # logging.debug(response.headers)
        # logging.debug(response.text)
        # logging.(response.text)

        if response.ok:
            logging.debug( "Response indicates success" )
            if response.content:
                logging.debug(response.content)
                if response.text:
                    logging.debug(json.dumps(response.json()))
                    return response.json()
            else:
                return None
        else:
            # anything other than "OK" from IDCS means error
            logging.error("Error making HTTP request")
            if response.text:
                logging.debug(response.text)
            else:
                logging.debug("No content to log")

            raise Exception( "HTTP request failed" )

