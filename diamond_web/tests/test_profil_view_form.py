"""Tests for views/profil.py (ProfilView) and forms/profil.py (ProfilForm)."""
import pytest
from django.urls import reverse

from diamond_web.forms.profil import ProfilForm
from diamond_web.tests.conftest import UserFactory


@pytest.mark.django_db
class TestProfilView:
    def test_requires_login(self, client):
        resp = client.get(reverse('user_profil'))
        assert resp.status_code in (302, 403)

    def test_get_prefills_names(self, client):
        user = UserFactory(first_name='Budi', last_name='Santoso')
        client.force_login(user)
        resp = client.get(reverse('user_profil'))
        assert resp.status_code == 200
        assert resp.context['form'].initial['first_name'] == 'Budi'
        assert resp.context['form'].initial['last_name'] == 'Santoso'

    def test_post_updates_name_only(self, client):
        user = UserFactory(first_name='Old', last_name='Name')
        client.force_login(user)
        resp = client.post(
            reverse('user_profil'),
            {'first_name': 'New', 'last_name': 'Name2'},
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.first_name == 'New'
        assert user.last_name == 'Name2'
        messages_list = list(resp.context['messages'])
        assert any('berhasil diperbarui' in str(m) for m in messages_list)

    def test_post_changes_password_keeps_session(self, client):
        user = UserFactory(first_name='A', last_name='B')
        user.set_password('OldPass123!')
        user.save()
        client.force_login(user)
        resp = client.post(
            reverse('user_profil'),
            {
                'first_name': 'A', 'last_name': 'B',
                'old_password': 'OldPass123!',
                'new_password1': 'BrandNewPass456!',
                'new_password2': 'BrandNewPass456!',
            },
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password('BrandNewPass456!')
        # Session should remain authenticated after password change.
        resp2 = client.get(reverse('user_profil'))
        assert resp2.status_code == 200

    def test_post_invalid_old_password_rejected(self, client):
        user = UserFactory(first_name='A', last_name='B')
        user.set_password('OldPass123!')
        user.save()
        client.force_login(user)
        resp = client.post(
            reverse('user_profil'),
            {
                'first_name': 'A', 'last_name': 'B',
                'old_password': 'WrongPass!',
                'new_password1': 'BrandNewPass456!',
                'new_password2': 'BrandNewPass456!',
            },
        )
        assert resp.status_code == 200
        assert not resp.context['form'].is_valid()
        user.refresh_from_db()
        assert not user.check_password('BrandNewPass456!')


@pytest.mark.django_db
class TestProfilForm:
    def test_new_password_requires_old_password(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={
                'first_name': 'A', 'last_name': 'B',
                'new_password1': 'AnotherNewPass1!',
                'new_password2': 'AnotherNewPass1!',
            },
            instance=user, user=user,
        )
        assert not form.is_valid()
        assert '__all__' in form.errors

    def test_wrong_old_password_rejected(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={
                'first_name': 'A', 'last_name': 'B',
                'old_password': 'nope',
                'new_password1': 'AnotherNewPass1!',
                'new_password2': 'AnotherNewPass1!',
            },
            instance=user, user=user,
        )
        assert not form.is_valid()
        assert 'old_password' in form.errors

    def test_mismatched_new_passwords_rejected(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={
                'first_name': 'A', 'last_name': 'B',
                'old_password': 'CurrentPass123!',
                'new_password1': 'AnotherNewPass1!',
                'new_password2': 'Different1!',
            },
            instance=user, user=user,
        )
        assert not form.is_valid()
        assert 'new_password2' in form.errors

    def test_weak_new_password_rejected_by_validators(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={
                'first_name': 'A', 'last_name': 'B',
                'old_password': 'CurrentPass123!',
                'new_password1': '123',
                'new_password2': '123',
            },
            instance=user, user=user,
        )
        assert not form.is_valid()
        assert 'new_password1' in form.errors

    def test_valid_password_change_saves(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={
                'first_name': 'Renamed', 'last_name': 'User',
                'old_password': 'CurrentPass123!',
                'new_password1': 'BrandNewPass456!',
                'new_password2': 'BrandNewPass456!',
            },
            instance=user, user=user,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.first_name == 'Renamed'
        assert saved.check_password('BrandNewPass456!')

    def test_no_password_change_only_updates_names(self):
        user = UserFactory()
        user.set_password('CurrentPass123!')
        user.save()
        form = ProfilForm(
            data={'first_name': 'OnlyName', 'last_name': 'Changed'},
            instance=user, user=user,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.first_name == 'OnlyName'
        assert saved.check_password('CurrentPass123!')
