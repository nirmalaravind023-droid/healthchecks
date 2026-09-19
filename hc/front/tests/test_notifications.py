from __future__ import annotations

import json
from datetime import timedelta as td

from django.utils.timezone import now

from hc.accounts.models import Project
from hc.api.models import Channel, Check, Notification
from hc.test import BaseTestCase


class NotificationsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = f"/projects/{self.project.code}/notifications/"

        self.check = Check.objects.create(project=self.project, name="Backup job")
        self.channel = Channel.objects.create(
            project=self.project,
            kind="email",
            value=json.dumps({"value": "alice@example.org", "up": True, "down": True}),
        )

    def test_it_shows_recent_notifications(self) -> None:
        old = Notification.objects.create(
            owner=self.check, channel=self.channel, check_status="down"
        )
        old.created = now() - td(hours=1)
        old.save()

        recent = Notification.objects.create(
            owner=self.check, channel=self.channel, check_status="up"
        )
        recent.created = now()
        recent.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "Recent Notifications", status_code=200)
        self.assertContains(r, "Backup job")
        self.assertContains(r, "Sent an email to alice@example.org")
        self.assertContains(r, "Up")
        self.assertContains(r, "Down")
        self.assertLess(
            r.content.index(str(recent.code).encode()),
            r.content.index(str(old.code).encode()),
        )

    def test_it_does_not_show_notifications_from_other_projects(self) -> None:
        other_project = Project.objects.create(owner=self.charlie)
        other_check = Check.objects.create(project=other_project, name="Charlies check")
        other_channel = Channel.objects.create(
            project=other_project,
            kind="email",
            value=json.dumps({"value": "charlie@example.org"}),
        )
        Notification.objects.create(
            owner=other_check, channel=other_channel, check_status="down"
        )

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertNotContains(r, "Charlies check", status_code=200)
        self.assertNotContains(r, "charlie@example.org")

    def test_team_member_access_works(self) -> None:
        Notification.objects.create(
            owner=self.check, channel=self.channel, check_status="down"
        )

        self.client.login(username="bob@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "Backup job", status_code=200)

    def test_it_checks_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)

        self.assertEqual(r.status_code, 404)

    def test_it_handles_empty_history(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "No notifications yet.", status_code=200)
