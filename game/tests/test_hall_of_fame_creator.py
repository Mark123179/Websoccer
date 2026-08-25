from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, ClubRecord, ClubRecordCorrectionRequest, League


class HallOfFameCreatorTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Rekordliga', country='DE')
        self.manager_user = User.objects.create_user('record-manager', password='test-password')
        self.staff_user = User.objects.create_user(
            'record-creator',
            password='test-password',
            is_staff=True,
        )
        self.club = Club.objects.create(
            name='Rekordverein',
            short_name='RV',
            founded_year=1900,
            budget=Decimal('0'),
            league=self.league,
            managed_by=self.manager_user.manager_profile,
        )

    def test_creator_record_tab_shows_all_three_record_sections(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse('creator_club_edit', kwargs={'club_id': self.club.pk}),
            {'tab': 'rekorde', 'rekordbereich': 'club'},
        )

        self.assertEqual(response.status_code, 200)
        sections = response.context['record_sections']
        self.assertEqual([len(section['rows']) for section in sections], [8, 8, 16])
        self.assertContains(response, 'Vereinsrekord')
        self.assertContains(response, 'Teuerster Einkauf')

    def test_creator_can_save_and_delete_a_real_record_without_touching_sim(self):
        ClubRecord.objects.create(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SIM,
            value_numeric=Decimal('12'),
            value_display='12',
            holder_name='Simulation',
        )
        self.client.force_login(self.staff_user)
        url = reverse(
            'creator_save_record',
            kwargs={'club_id': self.club.pk, 'record_key': 'top_scorer'},
        )
        response = self.client.post(url, {
            'value_display': '52 Tore',
            'value_numeric': '52',
            'holder_name': 'Echte Legende',
            'season': '2012/13',
            'record_date': '2013-05-18',
            'competition': 'Bundesliga',
            'context_line': 'Historischer Bestwert',
            'source_note': 'Vereinsarchiv',
        })

        self.assertRedirects(response, reverse('creator_club_edit', args=[self.club.pk]) + '?tab=rekorde')
        seed = ClubRecord.objects.get(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SEED,
        )
        self.assertEqual(seed.value_numeric, Decimal('52'))
        self.assertEqual(seed.holder_name, 'Echte Legende')
        self.assertEqual(
            ClubRecord.objects.get(
                club=self.club,
                record_key='top_scorer',
                source=ClubRecord.SOURCE_SIM,
            ).holder_name,
            'Simulation',
        )

        response = self.client.post(url, {'action': 'delete'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClubRecord.objects.filter(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SEED,
        ).exists())

    def test_creator_can_store_a_custom_club_record_label(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse(
                'creator_save_record',
                kwargs={'club_id': self.club.pk, 'record_key': 'club_empty_15'},
            ),
            {
                'custom_label': 'Meiste Derby-Siege',
                'value_display': '31',
                'value_numeric': '31',
                'holder_name': self.club.name,
            },
        )

        self.assertEqual(response.status_code, 302)
        record = ClubRecord.objects.get(
            club=self.club,
            record_key='club_empty_15',
            source=ClubRecord.SOURCE_SEED,
        )
        self.assertEqual(record.custom_label, 'Meiste Derby-Siege')

    def test_manager_request_is_moderated_into_seed_record(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            reverse('management_halloffame_correction_request'),
            {
                'room': 'club',
                'mode': 'echt',
                'record_key': 'biggest_win',
                'new_value': '9:0',
                'new_numeric_value': '9',
                'new_holder': self.club.name,
                'new_date': '1965-11-20',
                'new_season': '1965/66',
                'new_competition': 'Bundesliga',
                'new_context': 'Heimspiel',
                'source_reference': 'Vereinsarchiv, Saisonchronik 1965/66',
            },
        )
        self.assertRedirects(
            response,
            reverse('management_halloffame') + '?raum=club&modus=echt',
        )
        correction = ClubRecordCorrectionRequest.objects.get(club=self.club)
        self.assertEqual(correction.status, ClubRecordCorrectionRequest.STATUS_OPEN)

        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('creator_moderate_record_correction', kwargs={'request_id': correction.pk}),
            {'action': 'approve', 'decision_note': 'Quelle geprüft.'},
        )
        self.assertRedirects(response, reverse('creator_timeline_overview') + '?tab=rekorde')
        correction.refresh_from_db()
        self.assertEqual(correction.status, ClubRecordCorrectionRequest.STATUS_ACCEPTED)
        record = ClubRecord.objects.get(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SEED,
        )
        self.assertEqual(record.value_display, '9:0')
        self.assertEqual(record.competition, 'Bundesliga')

    def test_manager_cannot_submit_for_someone_elses_club(self):
        other_user = User.objects.create_user('other-manager', password='test-password')
        other_club = Club.objects.create(
            name='Fremdverein',
            short_name='FV',
            founded_year=1901,
            budget=Decimal('0'),
            league=self.league,
            managed_by=other_user.manager_profile,
        )
        self.client.force_login(self.manager_user)

        response = self.client.post(
            reverse('management_halloffame_correction_request'),
            {
                'club_id': other_club.pk,
                'room': 'club',
                'mode': 'echt',
                'record_key': 'biggest_win',
                'new_value': '7:0',
                'new_numeric_value': '7',
                'source_reference': 'Unzulässige Quelle',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClubRecordCorrectionRequest.objects.filter(club=other_club).exists())