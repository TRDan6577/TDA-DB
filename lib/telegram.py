#!/usr/bin/python3
# Author: Tom Daniels
# File: telegram.py
# Basic interactions with the telgram API

#############
## Imports ##
#############
import json
import logging
import requests
import socket
import sys


#############
## Classes ##
#############
class Telegram:

    def __init__(self, bot_id, chat_id, base_uri='https://api.telegram.org/'):
        """
        Purpose: Initializes the Telegram object and stores the chat/bot IDs
        @param   self (Object) - reference to the current instance of the class
        @param   bot_id (String) - the ID of the telegram bot
        @param   chat_id (String) - the ID of the telegram chat to send the message to
        @param   base_uri (string) - the protocol and hostname for the telegram API
        """
        self.base_uri = base_uri + 'bot{0}/'.format(bot_id)
        self.chat_id = chat_id


    def __send_request(self, endpoint, method, body={}, error_message='Error interacting with the telegram API'):
        """
        Purpose: Sends the HTTP request to the telegram API
        @param   self (Object) - reference to the current instance of the class
        @param   endpoint (String) - the API function to use
        @param   method (String) - the HTTP method to use for the endpoint
        @param   body (dict) - the body of the request in JSON (dict) format
        @param   error_message (String) - the message to log if the request fails
        @return  (dict) - the JSON returned from the API
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug('Entering send_request. Parameters are:\n\tendpoint: {0}\n\tmethod: {1}\n\tbody: {2}\n\terror_message: {3}'.format(endpoint, method, body, error_message))

        # Set the URI and add the chat ID to the body
        uri = '{0}{1}'.format(self.base_uri, endpoint)
        body['chat_id'] = self.chat_id

        # Only two methods allowed: GET and POST
        assert (method == 'GET' or method == 'POST'), "Error, method must be either 'GET' or 'POST'"
        try:
            if (method == 'GET'):
                response = requests.get(uri)
            else:
                response = requests.post(uri, body)
            assert response.ok, 'Response from the telegram API was status code {0}'.format(response.status_code)
        except Exception as e:
            logger.error('{0}. Error: {1}'.format(error_message, repr(e)))
            response = None

        return response


    #####################
    ## Class Functions ##
    #####################
    def send_error_message(self, message):
        """
        Purpose: Logs an error message, sends it over telegram, and quits the program
        @param   self (Object) - reference to the current instance of the class
        @param   message (string) - the error message
        @return  None
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()

        # Log the error, notify the user, and exit
        logger.error(message)
        self.send_message(message + "\nError from " + sys.argv[0] + " on " + socket.gethostname())
        logger.debug("Exiting...")
        exit()


    def send_message(self, message):
        """
        Purpose: Sends a telegram message. Docs: https://core.telegram.org/bots/api#sendmessage
        @param   self (Object) - reference to the current instance of the class
        @param   message (string) - the message to send
        @return  dict or None - the response from the server if the message is
                 successfully sent or None if the server doesn't respond with 200
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering send_message. Parameters are:\n\tmessage: {0}".format(message))
        
        # Send the message
        response = self.__send_request('sendMessage', 'POST', body={'text': message})
        return json.loads(response.text)


    def get_pinned_message(self):
        """
        Purpose: Gets the most recently pinned chat message
        @param   self (Object) - reference to the current instance of the class
        @return  (dict) - the JSON response from the telegram API. This is a message object
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_pinned_message")

        # Get the chat object
        response = self.__send_request('getChat', 'POST')

        # Return the pinned message
        try:
            pinned_message = json.loads(response.text)['result']['pinned_message']
        except KeyError:
            logger.warning("JSON response doesn't contain a pinned message. JSON: {0}".format(response.text))
            pinned_message = None

        return pinned_message


    def pin_message(self, message_id):
        """
        Purpose: Pins the specified message_id to the chat
        @param   self (Object) - reference to the current instance of the class
        @param   message_id (String) - the telegram message ID of the message to be pinned
        @return  (NoneType) - nada
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug('Entering pin_message. Parameters are:\n\tmessage_id: {0}'.format(message_id))

        # Pin the message in the chat
        body = {
            'message_id': message_id,
            'disable_notification': True
        }
        response = self.__send_request('pinChatMessage', 'POST', body)

        return None


    def get_updates():
        """
        Purpose: Retrieves any updates to the chat
        @param   self (Object) - reference to the current instance of the class
        @return  (dict) - JSON response of updates
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug('Entering get_updates')
        
        # Get all the new updates
        response = self.__send_request('getUpdates', 'GET')
        return json.loads(response.text)


    def unpin_all_chat_messages():
        """
        Purpose: Unpins all the pinned chat messages
        @param   self (Object) - reference to the current instance of the class
        @return  (NoneType) - nada
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug('Entering unpin_all_chat_messages')

        # Unpin all the messages
        self.__send_request('unpinAllChatMessages', 'POST')
        return None

