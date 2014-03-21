#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# vim: set expandtab tabstop=4 shiftwidth=4 :

# This is an Exocortex subclass that implements a Twitterbot.  It interfaces
# with Twitter's API and carries out the following functions:

# TODO:
# - Get replies to the user's account.
# - Pull top/all tweets on trending topics.
# - Monitor trending topics and alert if specific search terms show up in the
#   list.
# - Monitor the activity of a particular user.  Archive the user's tweets for
#   searching.
# - Monitor the stream for a particular hashtag.  Scan for particular users or
#   keywords.
# - Add support for the Statusnet API.
#   Twitter-compatible API: http://status.net/wiki/Twitter-compatible_API
# - Make it possible to do a file:send to the bot of the user's tweet archive
#   and it'll load the tweets.csv file into a database server it's connected
#   to.

# By: The Doctor <drwho at virtadpt dot net>
#     0x807B17C1 / 7960 1CDC 85C9 0B63 8D9F  DD89 3BD8 FF2B 807B 17C1

# License: GPLv3
# Pre-requisite modules have their own licenses.

# Load modules.
import datetime
from exocortex import ExocortexBot
import os
import string
import sys
import tweepy
from tweepy import StreamListener

# Classes.
""" This class implements an interface to the Twitter API which allows the bot
to extract information from Twitter and post stuff to the user's timeline.
The user must have a Twitter account and must have applied for and received
access tokens for Twitter
(https://dev.twitter.com/docs/auth/obtaining-access-tokens).  The API keys
go in your config file.
"""
class TwitterBot(ExocortexBot):
    # Class attributes go here so they're easy to find.
    # Access keys that cryptographically authenticate requests from a
    # particular user to the Twitter API server.
    api_key = ""
    api_secret = ""

    # OAuth access tokens that identify the application and user to the API
    # server.
    access_token = ""
    access_token_secret = ""

    # OAuth authenticator and API interface objects that connect to the
    # Twitter API application server.
    auth = ""
    api = ""

    # Twitter developer account interface objects.  I don't have a better word
    # to describe this, so that's what it is for now.  Blame the "I'm screwing
    # around with this API" test script I wrote.
    user = ""

    # A list of commands defined on bots descended from this particular class.
    # This list is inherited from the ExocortexBot base class, but is extended
    # to include TwitterBot-specific commands.
    commands = ExocortexBot.commands
    twitterbot_commands = ['twitter status', 'search hashtag/for',
        'post tweet/post to twitter', 'list/find trends', 'get archive/tweets',
        'get my tweets', 'query user', 'query user activity/timeline' ]
    commands = commands + twitterbot_commands

    # API error catcher.
    api_error = ""

    # List of Twitter WOEID's that have trending topics.  We need to cache
    # this value for later commands.
    woeid = []

    """ Default constructor for the TwitterBot class.  Inherits much of its
    code from ExocortexBot.__init__(), and in fact calls it to set up the
    basic stuff. """
    def __init__(self, owner, botname, jid, password, room, room_announcement,
        imalive, responsefile, function, api_key, api_secret, access_token,
        access_token_secret):

        # Copy the TwitterBot-specific constructor args into class attributes
        # to make them easier to work with.
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret

        # Call the base class' constructor.
        ExocortexBot.__init__(self, owner, botname, jid, password, room,
            room_announcement, imalive, responsefile, function)

        # Authenticate with the Twitter API server.
        self.auth = tweepy.OAuthHandler(self.api_key, self.api_secret)
        self.auth.set_access_token(self.access_token, self.access_token_secret)

        # Create an API interface object.
        self.api = tweepy.API(self.auth)

        # Create an interface to the bot's owner's Twitter dev account.
        try:
            self.send_message(mto=self.owner,
                mbody="Trying to contact Twitter API server.  Please wait...")
            self.user = self.api.me()
        except tweepy.error.TweepError as api_error:
            print "\nERROR: " + api_error.reason + ".  Trying again...\n"
            self.send_message(mto=self.owner,
                mbody="Unable to contact Twitter API server.  Error message: %s.  Retrying..." % api_error.reason)

    """ Event handler that fires whenever a message is sent to this JID. The
    argument 'msg' represents a message stanza.  This method implements
    Twitter-specific commands. """
    def message(self, msg):
        # Potential message types: normal, chat, error, headline, groupchat
        if msg['type'] in ('chat', 'normal'):

            # Extract whom the message came from.
            msg_from = str(msg.getFrom())
            msg_from = string.split(msg_from, '/')[0]

            # If the message did not come from the bot's owner, ignore by
            # bouncing out of this method.
            if msg_from != self.owner:
                return

            # To make parsing easier, lowercase the message body before matching
            # against it.
            message = msg['body'].lower()

            # Parse the message text for commands.
            # Class-specific help message
            if "help" in message:
                self.send_message(mto=msg['from'],
                    mbody="Hello.  My name is %s.  %s  In addition to the usual ExocortexBot commands, I also support the following specialized commands:\n\n%s\n" % (self.botname, self.function, str(self.commands)))
                self.send_message(mto=msg['from'],
                    mbody="You can search Twitter for hashtags or arbitrary terms with the commands 'search hashtag #somehashtag' or 'search for somesearchterm'.\n")
                self.send_message(mto=msg['from'],
                    mbody="You can post something to Twitter with the commands 'post tweet <140 characters here>' or 'post to twitter <140 characters here>'.\n")
                self.send_message(mto=msg['from'],
                    mbody="You can search Twitter for trending topics around the world with the commands 'list trends <geographic location>' or 'find trends <geographic location>'.\n")
                self.send_message(mto=msg['from'],
                    mbody="You can follow trends on Twitter with the command 'follow trend <keyword>'.\n")
                self.send_message(mto=msg['from'],
                    mbody="You can query a Twitter user's profile with the command 'query user <Twitter username>'.\n")
                self.send_message(mto=msg['from'],
                    mbody="You can query a Twitter user's recent activity with the command 'query user activity <Twitter username> <number of tweets (default: 20)>' or 'query user timeline <username> <number of tweets>' .\n")
                return

            # The user wants only the status of the Twitter connection.
            if 'twitter status' in message:
                self.send_message(mto=msg['from'],
                    mbody="Polling Twitter status.  Please wait...")
                status = self._twitter_status()
                self.send_message(mto=msg['from'], mbody=status)
                return

            # The user wants to execute a hashtag search.
            if 'search hashtag' in message or 'search for' in message:
                hashtag = message.split()[-1]
                if hashtag == 'hashtag':
                    self.send_message(mto=self.owner,
                        mbody="No hashtag was specified.")
                    return
                else:
                    self.send_message(mto=self.owner,
                        mbody="Executing search for term %s.  Just a moment." %
                        hashtag)
                hashtag_results = self.api.search(q=hashtag,
                    result_type='recent')
                number_of_results = len(hashtag_results)

                # If nothing came back, bounce.
                if not number_of_results:
                    response = "No results were returned for search on " + hashtag + ".'"
                    self.send_message(mto=self.owner, mbody=response)
                    return
                else:
                    response = str(number_of_results) + " tweets were found."
                    self.send_message(mto=self.owner, mbody=response)

                # Build response and send back to user.
                response = ""
                for tweet in hashtag_results:
                    response_line = "@" + tweet.user.name + ": " + tweet.text + "\n" + "Retweeted " + str(tweet.retweet_count) + " times.\n\n"
                    response = response + response_line
                self.send_message(mto=self.owner, mbody=response)
                return

            # The user wants to update their Twitter timeline.
            if 'post tweet' in message or 'post to twitter' in message:
                # Remove the command from the message.
                if 'post tweet' in message:
                    message = message.replace('post tweet', '')
                if 'post to twitter' in message:
                    message = message.replace('post to twitter', '')
                message = message.strip()

                # Do some sanity checking - if the tweet's longer than 140
                # characters, don't bother trying.
                if len(message) > 140:
                    self.send_message(mto=self.owner,
                        mbody="Your message is longer than 140 characters.  I can't post this.")
                    return

                # Post the message to Twitter.
                self.send_message(mto=msg['from'],
                    mbody="Posting message to Twitter.  Please wait...")
                posted_to_twitter = self._post_to_twitter(message)
                if posted_to_twitter == True:
                    self.send_message(mto=self.owner,
                        mbody="Status update successfully posted to Twitter.")
                return

            # The user wants a list of trending topics on Twitter.
            if 'list trends' in message or 'find trends' in message:
                # Reset the list of WOEID's.
                self.woeid = []

                # Strip the command string out of the message, leaving only
                # the keywords we want to work with.
                message = message.replace('list trends', '')
                message = message.replace('find trends', '')
                message = message.strip()
                location = message.title()

                # If the user asks for help or does not give a location,
                # send a help message.
                if message == 'help' or message == '':
                    self.send_message(mto=self.owner,
                        mbody="Twitter maps trending topics by geographic location, so this command must be used with the name of a Country or city.")
                    return

                # Inform the user that the search is about to begin.
                self.send_message(mto=self.owner,
                    mbody="Searching trending topics on Twitter for %s..." %
                           location)

                # Pull the current database of trending locations around the
                # world from the API server.  This is usually in the ballpark
                # of 100kb.
                try:
                    trending_locations = self.api.trends_available()
                except tweepy.error.TweepError as api_error:
                    self.send_message(mto=self.owner,
                        mbody="Unable to contact Twitter API server.  Error message: %s." % api_error.reason)
                    return

                # Search for the named location in that database.  There are
                # two possible fields that it can appear in, either in
                # 'country' or in 'name' (which can be either the name of the
                # country or a more specific place in that country).  Store
                # the WOEID's in a list.
                for locale in trending_locations:
                    if locale['country'] == location:
                        if locale['woeid'] not in self.woeid:
                            self.woeid.append(locale['woeid'])
                    if locale['name'] == location:
                        if locale['woeid'] not in self.woeid:
                            self.woeid.append(locale['woeid'])

                # Send a response back to the user.  If there are no results,
                # there's no sense in going through the rest of the method.
                if not len(self.woeid):
                    response = "There are currently no trending topics in " + location + " at this time."
                    self.send_message(mto=self.owner, mbody=response)
                    return

                # There are results, so treat them appropriately.
                if len(self.woeid) == 1:
                    response = "There is one trending topic in " + location + " at this time."
                if len(self.woeid) > 1:
                    response = "There are " + str(len(self.woeid)) + " trending topics in " + location + " at this time."
                self.send_message(mto=self.owner, mbody=response)

                # Query the API server for as many trending terms (Twitter
                # limits this to 10) as we can get for every WOEID.
                response = "The following terms are trending in location:\n"
                for locale in self.woeid:
                    try:
                        trends = self.api.trends_place(id=locale)
                    except tweepy.error.TweepError as api_error:
                        self.send_message(mto=self.owner,
                            mbody="Unable to contact Twitter API server.  Error message: %s." % api_error.reason)
                        return

                    # Walk through the list of trending locations and assemble
                    # a list of terms and URLs that the user can click on to
                    # look at the lists of tweets.
                    for i in trends[0]['trends']:
                        response = response + "Trending term: " + i['name']
                        response = response + "  URL: " + i['url'] + "\n"

                # Send the response back to the user.
                self.send_message(mto=self.owner, mbody=response)
                return

            # The user asks to have their content archive downloaded from
            # Twitter.  The bot can't do that, but it can tell you how to do
            # that.
            if "get archive" in message or "get tweets" in message or "get my tweets" in message:
                self._get_my_tweets()

            # Query a user's recent timeline activity.
            if "query user activity" in message or 'query user timeline' in message:
                # Extract the user's Twitter username and number of tweets to
                # pull.
                message = message.replace('query user activity', '')
                message = message.replace('query user timeline', '')
                queried_user = message.split(' ')[1].strip()

                # This is a little hacky, but I can't think of a better way
                # to take into account situations where the user doesn't
                # supply the number of tweets to pull.
                number_of_tweets = ""
                try:
                    number_of_tweets = message.split()[2].strip()
                    number_of_tweets = int(number_of_tweets)
                except:
                    number_of_tweets = 20

                # Sanity check the number of tweets the user is asking for.
                if number_of_tweets < 0:
                    self.send_message(mto=self.owner, mbody="ERROR: You cannot request a negative number of tweets.  That doesn't make any sense.")
                    return
                if number_of_tweets > 3200:
                    self.send_message(mto=self.owner, mbody="ERROR: The Twitter API server limits the number of tweets you can request from someone's timeline to 3200.")
                    return
                self._query_user_activity(queried_user, number_of_tweets)
                return

            # Query a user's profile.
            if "query user" in message:
                # Extract the Twitter username
                queried_user = message.replace('query user', '').strip()
                self._query_user(queried_user)
                return

            # Class-specific commands out of the way, call the message parser of
            # the base class.
            ExocortexBot.message(self, msg)

    """ This method only displays the status of the Twitter API server
    connection.  It can be called by self._process_status() but doesn't have
    to be. """
    def _twitter_status(self):
        number_of_followers = ""
        status = ""

        # Query the number of followers the user's account has.  If the query
        # goes through the Twitter API connection is up.
        try:
            number_of_followers = len(self.api.followers())
        except tweepy.error.TweepError as api_error:
            return "ERROR: " + api_error.reason
        if number_of_followers:
            status = self.botname + " has an active connection to the Twitter API service.\n"

        # Query the number of API requests available in this 60 minute
        # timespan and when the hit counter will reset.
        try:
            limit_status = self.api.rate_limit_status()
        except tweepy.error.TweepError as api_error:
            return "ERROR: " + api_error.reason

        # Assemble the status message to transmit to the bot's owner.
        hits_remaining = limit_status['resources']['application']['/application/rate_limit_status']['remaining']
        hits_reset = limit_status['resources']['application']['/application/rate_limit_status']['reset']
        reset_time = datetime.datetime.fromtimestamp(int(hits_reset)).strftime('%H:%M:%S hours on %Y/%m/%d')
        status = status + "This bot has " + str(hits_remaining) + " API hits remaining until Twitter temporarily cuts it off.\n"
        status = status + "The API hit counter will refresh at " + reset_time + "."
        return(status)

    """ Helper method that posts updates to the bot owner's Twitter feed.
    Returns a success/fail to the callling method.  Surprisingly simple,
    really. """
    def _post_to_twitter(self, message):
        try:
            self.api.update_status(message)
        except tweepy.error.TweepError as api_error:
            self.send_message(mto=self.owner,
                mbody="Unable to post to Twitter.  Error message: %s." % api_error.reason)
            return False
        return True

    """ Twitter doesn't actually make it possible to download your tweets via
    their API, but they will let you download a package of them to use
    offline.  Inform the user about this if they ask. """
    def _get_my_tweets(self):
        response = "The Twitter API server does not let you download your Twitter timeline.  Twitter will, however, let you download the contents of your timeline.  They'll generate a .zip file for you to download containing, among other things, a file called 'tweets.csv' which you can import into a database.\n\nClick on this link to request your tweet archive: https://twitter.com/settings/account"
        self.send_message(mto=self.owner, mbody=response)

    """ Given a Twitter username, pull their most recent timeline activity.
    Defaults to the 20 most recent tweets, but the API server will let you
    request up to 3200 tweets. """
    def _query_user_activity(self, user, tweet_count=20):
        queried_user = user.replace('@', '')
        user_timeline = ""

        # Request a user timeline object from the API server.
        try:
            user_timeline = self.api.user_timeline(screen_name=queried_user,
                include_rts=True, count=tweet_count)
        except tweepy.error.TweepError as api_error:
            self.send_message(mto=self.owner,
                mbody="Unable to access user's timeline.  Error message: %s." % api_error.reason)
            return
        self.send_message(mto=self.owner,
            mbody="Here are the last %i tweets @%s has posted:\n" % (tweet_count, queried_user))

        # Walk through the user's most recent tweets, and for each one
        # assemble a private chat message to the bot's owner.
        for tweet in user_timeline:
            message = str(tweet.created_at) + ": " + tweet.text
            if tweet.coordinates:
                message = message + "Coordinates: " + str(tweet.coordinates)
            if tweet.entities['urls']:
                message = message + "\n" + tweet.entities['urls'][0]['expanded_url']
            message = message + "\n"
            self.send_message(mto=self.owner, mbody=message)
        return

    """ Given a Twitter username, pull their profile.  Send it back to the
    bot's owner in a private chat. """
    def _query_user(self, user):
        # For consistency, remove a leading @ symbol if it exists.
        queried_user = user.replace('@', '')
        queried_user_profile = ""

        # Request a user object from the API server.
        try:
            queried_user_profile = self.api.get_user(queried_user)
        except tweepy.error.TweepError as api_error:
            self.send_message(mto=self.owner,
                mbody="Unable to pull user profile.  Error message: %s." % api_error.reason)
            return

        # Build a profile and send it back to the user.
        profile = "Username: @" + queried_user_profile.screen_name + "\n"
        profile = profile + "Name: " + queried_user_profile.name + "\n"
        profile = profile + "Description: " + queried_user_profile.description + "\n"
        profile = profile + "Twitter Internal ID: " + str(queried_user_profile.id) + "\n"
        profile = profile + "Number of followers: " + str(queried_user_profile.followers_count) + "\n"
        profile = profile + "Total number of tweets: " + str(queried_user_profile.statuses_count)
        self.send_message(mto=self.owner, mbody=profile)
        return

# Core code...
if __name__ == '__main__':
    # Self tests go here...
    sys.exit(0)
# Fin.