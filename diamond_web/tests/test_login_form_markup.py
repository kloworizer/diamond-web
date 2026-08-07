"""Tests for the login page: that it still logs people in, and still autofills.

The autocomplete tokens and the label/id pairing are the whole reason a browser
password manager offers a saved credential. They are invisible in the rendered
design — nothing looks wrong when they are missing — so they are pinned here
rather than left to be noticed the next time somebody cannot sign in quickly.
"""
import re

import pytest
from django.urls import reverse

from diamond_web.tests.conftest import UserFactory


def _login_page(client):
    return client.get(reverse('login')).content.decode()


def _input_attrs(page, name):
    """Return the attributes of the ``<input name="...">`` tag as a dict."""
    match = re.search(r'<input\b[^>]*\bname="%s"[^>]*>' % re.escape(name), page)
    assert match, f'no input named {name} on the login page'
    return dict(re.findall(r'(\w[\w-]*)="([^"]*)"', match.group(0)))


@pytest.mark.django_db
class TestLoginStillWorks:
    def test_page_renders(self, client):
        assert client.get(reverse('login')).status_code == 200

    def test_valid_credentials_sign_the_user_in(self, client):
        """The field names are Django's, so renaming them would break login."""
        user = UserFactory()
        user.set_password('rahasia-sekali')
        user.save()

        resp = client.post(
            reverse('login'),
            {'username': user.username, 'password': 'rahasia-sekali'},
        )

        assert resp.status_code == 302
        assert client.session.get('_auth_user_id') == str(user.pk)

    def test_wrong_password_does_not_sign_in(self, client):
        user = UserFactory()
        user.set_password('rahasia-sekali')
        user.save()

        resp = client.post(
            reverse('login'), {'username': user.username, 'password': 'salah'}
        )

        assert resp.status_code == 200
        assert '_auth_user_id' not in client.session

    def test_form_has_no_action_so_the_next_parameter_survives(self, client):
        """`?next=` is read off the URL, so the form must post back to it.

        Hard-coding action="/login/" would silently drop the redirect target and
        send everyone to the default landing page after signing in.
        """
        page = _login_page(client)
        form_tag = '<form' + page.split('<form', 1)[1].split('>', 1)[0]
        assert 'action=' not in form_tag


@pytest.mark.django_db
class TestAutofillSignals:
    def test_username_field_is_tagged_for_autofill(self, client):
        attrs = _input_attrs(_login_page(client), 'username')
        assert attrs['autocomplete'] == 'username'
        assert attrs['id'] == 'id_username'

    def test_password_field_is_tagged_for_autofill(self, client):
        attrs = _input_attrs(_login_page(client), 'password')
        assert attrs['autocomplete'] == 'current-password'
        assert attrs['id'] == 'id_password'
        assert attrs['type'] == 'password'

    def test_both_fields_have_a_label_bound_by_id(self, client):
        """A placeholder is not a label — "NIP9 SIKKA" names nothing to a scanner."""
        page = _login_page(client)
        labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', page))
        assert {'id_username', 'id_password'} <= labelled

    def test_style_and_title_sit_inside_the_head(self, client):
        """Markup before <head> pushes the whole head into the body.

        The page used to open with a stray comment and a <style> block before
        <head>, which makes the document invalid and its tree unpredictable —
        the ground a form scanner walks.
        """
        page = _login_page(client)
        head = page[page.index('<head'):page.index('</head>')]
        assert '<style>' in head
        assert '<title>' in head
        assert not re.search(r'<html[^>]*>\s*[^\s<]', page)

    def test_password_toggle_is_still_there_and_out_of_the_tab_order(self, client):
        """The peek button stays; it is not what blocks autofill.

        It has to stay type=button so it never submits the form, and
        tabindex=-1 so tabbing goes password -> submit, not password -> eye.
        """
        page = _login_page(client)
        toggle = re.search(r'<button\b[^>]*id="toggle-password"[^>]*>', page)
        assert toggle
        assert 'type="button"' in toggle.group(0)
        assert 'tabindex="-1"' in toggle.group(0)
