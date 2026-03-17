from django.test import TestCase
from unittest.mock import MagicMock, patch
from dental_ussd.models import Patient, Appointment, ClinicAvailability
from dental_ussd import utils
import datetime


def make_ussd_request(session_data=None):
    """Helper to create a mock USSD request with the given session data."""
    req = MagicMock()
    req.session = session_data or {}
    return req


class AuthenticateUserTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            mobile_number='+67570001111',
            name='Test Patient'
        )

    def test_existing_user_returns_patient(self):
        req = make_ussd_request({'phone_number': '+67570001111'})
        result = utils.authenticate_user(req)
        self.assertEqual(result, self.patient)

    def test_non_existing_user_returns_none(self):
        req = make_ussd_request({'phone_number': '+99900000000'})
        result = utils.authenticate_user(req)
        self.assertIsNone(result)


class RegisterUserTest(TestCase):
    def test_new_registration_creates_patient(self):
        req = make_ussd_request({
            'phone_number': '+67570001111',
            'patient_name': 'New Patient'
        })
        result = utils.register_user(req)
        self.assertIsInstance(result, Patient)
        self.assertEqual(result.mobile_number, '+67570001111')
        self.assertEqual(result.name, 'New Patient')

    def test_duplicate_phone_returns_existing_patient(self):
        Patient.objects.create(mobile_number='+67570001111', name='Existing')
        req = make_ussd_request({
            'phone_number': '+67570001111',
            'patient_name': 'Different Name'
        })
        result = utils.register_user(req)
        self.assertIsInstance(result, Patient)
        # Should return the existing patient, not create a new one
        self.assertEqual(result.name, 'Existing')
        self.assertEqual(Patient.objects.filter(mobile_number='+67570001111').count(), 1)


class FetchAvailableAppointmentSlotTest(TestCase):
    def setUp(self):
        self.slot = ClinicAvailability.objects.create(
            clinic_location='Dental Clinic A',
            appointment_type='Checkup',
            available_slots=3,
            appointment_date=datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.timezone.utc)
        )

    def test_returns_slots_when_available(self):
        req = make_ussd_request({'appointment_type': 'checkup'})
        result = utils.fetch_available_appointment_slot(req)
        self.assertIsNotNone(result)
        self.assertIn(self.slot.pk, result)

    def test_returns_none_when_no_slots(self):
        req = make_ussd_request({'appointment_type': 'filling'})
        result = utils.fetch_available_appointment_slot(req)
        self.assertIsNone(result)

    def test_returns_none_when_no_appointment_type(self):
        req = make_ussd_request({})
        result = utils.fetch_available_appointment_slot(req)
        self.assertIsNone(result)


class BookAppointmentTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            mobile_number='+67570001111',
            name='Test Patient'
        )
        self.slot = ClinicAvailability.objects.create(
            clinic_location='Dental Clinic A',
            appointment_type='Checkup',
            available_slots=3,
            appointment_date=datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.timezone.utc)
        )

    def test_happy_path_creates_appointment(self):
        req = make_ussd_request({
            'phone_number': '+67570001111',
            'appointment_slot': self.slot.pk,
        })
        result = utils.book_appointment(req)
        self.assertIsInstance(result, Appointment)
        self.assertEqual(result.patient, self.patient)
        self.assertEqual(result.appointment_type, 'Checkup')

    def test_decrements_available_slots(self):
        req = make_ussd_request({
            'phone_number': '+67570001111',
            'appointment_slot': self.slot.pk,
        })
        utils.book_appointment(req)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.available_slots, 2)

    def test_missing_patient_returns_none(self):
        req = make_ussd_request({
            'phone_number': '+00000000000',
            'appointment_slot': self.slot.pk,
        })
        result = utils.book_appointment(req)
        self.assertIsNone(result)

    def test_invalid_slot_returns_none(self):
        req = make_ussd_request({
            'phone_number': '+67570001111',
            'appointment_slot': 99999,
        })
        result = utils.book_appointment(req)
        self.assertIsNone(result)


class CancelAppointmentTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            mobile_number='+67570001111',
            name='Test Patient'
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            appointment_type='Checkup',
            clinic_location='Dental Clinic A',
            appointment_date=datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.timezone.utc),
            status='scheduled'
        )

    def test_happy_path_cancels_appointment(self):
        req = make_ussd_request({'selected_appointment': self.appointment.pk})
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')

    def test_invalid_appointment_pk_returns_none(self):
        req = make_ussd_request({'selected_appointment': 99999})
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)

    def test_missing_selected_appointment_returns_none(self):
        req = make_ussd_request({})
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)

