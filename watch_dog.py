#!/usr/bin/env python
# coding: utf-8

import urllib
import urllib2
import json as jsonlib
import argparse
from datetime import datetime, timedelta
import sys
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()


class Response(object):

    def __init__(self, response):
        self.raw_response = response
        self._content = None

    @property
    def content(self):
        if self._content is not None:
            return self._content
        content = self._content = self.raw_response.read()
        return content

    def json(self):
        return jsonlib.loads(self.content)


class Session(object):

    def __init__(self):
        self.opener = urllib2.build_opener()

    def post(self, url, query=None, form=None, json=None, headers=None):
        headers = headers or {}
        if query:
            url = "%s?%s" % (url, urllib.urlencode(query))

        if json:
            data = jsonlib.dumps(json)
            headers["Content-Type"] = "application/json"
        elif form:
            data = urllib.urlencode(form)
        else:
            data = ""

        response = self.opener.open(urllib2.Request(
            url, data, headers=headers,
        ))

        return Response(response)

    def get(self, url, data=None, headers=None):
        headers = headers or {}
        if data:
            url = "%s?%s" % (url, urllib.urlencode(data))

        response = self.opener.open(urllib2.Request(
            url, headers=headers,
        ))

        return Response(response)


class APPState(object):
    running = "running"
    stoped = "stopped"
    pending = "pending"


class WatchDog(object):
    def __init__(self, access_token, apps):
        self.session = Session()
        self.apps = apps
        self.request_headers = {
            "Authorization": "token %s" % access_token
        }

    def gen_apps(self):
        response = self.session.get(
            "https://openapi.daocloud.io/v1/apps",
            headers=self.request_headers,
        )
        result = response.json()
        for app in result["app"]:
            yield app

    def log_app_info(self, app):
        logger.info("app name: %s", app.get("name"))
        logger.info("app id: %s", app.get("id"))
        logger.info("app state: %s", app.get("state"))
        logger.info("app created_at: %s", app.get("created_at"))
        logger.info("app last_operated_at: %s", app.get("last_operated_at"))

    def try_start_app(self, app):
        try:
            if app["state"] != APPState.stoped:
                return
            response = self.session.post(
                "https://openapi.daocloud.io/v1/apps/{app_id}/actions/start".format(
                    app_id=app["id"],
                ), headers=self.request_headers,
            )
            result = response.json()
            logger.info("start app[%s]: %s", app["name"], result["action_id"])
        except Exception as err:
            logger.error(err, exc_info=True)

    def try_restart_app(self, app, time_before):
        try:
            if app["state"] != APPState.running:
                return
            import pdb; pdb.set_trace()
            last_operated_at = datetime.strptime(
                app["last_operated_at"], "%Y-%m-%dT%H:%M:%S+00:00",
            )
            if last_operated_at < time_before:
                response = self.session.post(
                    "https://openapi.daocloud.io/v1/apps/{app_id}/actions/restart".format(
                        app_id=app["id"],
                    ), headers=self.request_headers,
                )
            result = response.json()
            logger.info("restart app[%s]: %s", app["name"], result["action_id"])
        except Exception as err:
            logger.error(err, exc_info=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("access_token")
    parser.add_argument("-a", "--apps", nargs="+")
    parser.add_argument("-t", "--ttl", type=int, default=0)
    args = parser.parse_args()

    dog = WatchDog(args.access_token, args.apps)
    for app in dog.gen_apps():
        app_name = app["name"]
        if args.apps and app_name not in args.apps:
            continue

        logger.info("check app[%s]", app_name)
        dog.log_app_info(app)
        dog.try_start_app(app)
        if args.ttl:
            time_before = datetime.utcnow() - timedelta(minutes=args.ttl)
            dog.try_restart_app(app, time_before)


if __name__ == "__main__":
    main()
