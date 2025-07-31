import requests
import json, urllib
from datetime import datetime
from six.moves.urllib.request import urlopen

class InstagramConnector:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url_instagram = "https://graph.instagram.com"
        self.base_url_facebook = "https://graph.facebook.com"

    def get_user_id(self, username):
        params = {
            "access_token": self.access_token,
            "fields": "id"
        }

        response = requests.get(f"{self.base_url_instagram}/{username}", params=params)
        return response.json()

    def get_posts(self, user_id, start_date, end_date, hashtag=None):
        params = {
            "access_token": self.access_token,
            "fields": "id,caption,media_type,media_url,timestamp",
            "since": start_date,
            "until": end_date
        }
        if hashtag:
            params["hashtag"] = hashtag

        response = requests.get(f"{self.base_url_instagram}/{user_id}/media", params=params)
        return response.json()

    def get_reels(self, user_id, start_date, end_date, hashtag=None):
        params = {
            "access_token": self.access_token,
            "fields": "id,caption,media_type,media_url,timestamp",
            "since": start_date,
            "until": end_date
        }
        if hashtag:
            params["hashtag"] = hashtag

        response = requests.get(f"{self.base_url_instagram}/{user_id}/reels", params=params)
        return response.json()

    def get_stories(self, user_id, start_date, end_date, hashtag=None):
        params = {
            "access_token": self.access_token,
            "fields": "id,caption,media_type,media_url,timestamp",
            "since": start_date,
            "until": end_date
        }
        if hashtag:
            params["hashtag"] = hashtag

        response = requests.get(f"{self.base_url_instagram}/{user_id}/stories", params=params)
        return response.json()

    def get_profile(self, user_id):
        params = {
            "access_token": self.access_token,
            "fields": "id,username,profile_picture_url"
        }

        response = requests.get(f"{self.base_url_instagram}/{user_id}", params=params)
        return response.json()

    def get_comments(self, post_id):
        params = {
            "access_token": self.access_token,
            "fields": "id,text,username"
        }

        response = requests.get(f"{self.base_url_facebook}/v22.0/{post_id}/comments", params=params)
        return response.json()

    def get_metrics(self, post_id):
        params = {
            "access_token": self.access_token,
            "fields": "engagement,reach,impressions"
        }

        response = requests.get(f"{self.base_url_instagram}/{post_id}/insights", params=params)
        return response.json()