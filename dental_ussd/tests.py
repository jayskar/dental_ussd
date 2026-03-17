from django.test import TestCase
from unittest.mock import MagicMock, patch
from dental_ussd.models import Patient, Appointment, ClinicAvailability
from dental_ussd import utils
from dental_ussd.views import DentalAppUssdGateway
import datetime
import re


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
        self.other_patient = Patient.objects.create(
            mobile_number='+67570002222',
            name='Other Patient'
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            appointment_type='Checkup',
            clinic_location='Dental Clinic A',
            appointment_date=datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.timezone.utc),
            status='scheduled'
        )

    def test_happy_path_cancels_appointment(self):
        req = make_ussd_request({
            'selected_appointment': self.appointment.pk,
            'phone_number': '+67570001111',
        })
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')

    def test_invalid_appointment_pk_returns_none(self):
        req = make_ussd_request({
            'selected_appointment': 99999,
            'phone_number': '+67570001111',
        })
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)

    def test_missing_selected_appointment_returns_none(self):
        req = make_ussd_request({})
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)

    def test_cannot_cancel_other_users_appointment(self):
        """A user cannot cancel an appointment that belongs to a different patient."""
        req = make_ussd_request({
            'selected_appointment': self.appointment.pk,
            'phone_number': '+67570002222',  # different patient
        })
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)
        self.appointment.refresh_from_db()
        # Appointment must still be 'scheduled' — not cancelled
        self.assertEqual(self.appointment.status, 'scheduled')

    def test_missing_phone_number_returns_none(self):
        req = make_ussd_request({'selected_appointment': self.appointment.pk})
        result = utils.cancel_appointment(req)
        self.assertIsNone(result)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'scheduled')


class PhoneNumberValidatorTest(TestCase):
    """Tests for the phone number regex validator on the Patient model."""

    def test_valid_phone_number_with_plus(self):
        from django.core.exceptions import ValidationError
        from dental_ussd.models import phone_validator
        # Should not raise
        phone_validator('+67570001111')
        phone_validator('+1234567890')

    def test_valid_phone_number_without_plus(self):
        from dental_ussd.models import phone_validator
        phone_validator('67570001111')

    def test_invalid_phone_number_too_short(self):
        from django.core.exceptions import ValidationError
        from dental_ussd.models import phone_validator
        with self.assertRaises(ValidationError):
            phone_validator('123')

    def test_invalid_phone_number_with_letters(self):
        from django.core.exceptions import ValidationError
        from dental_ussd.models import phone_validator
        with self.assertRaises(ValidationError):
            phone_validator('abc123456789')


class InputValidationViewTest(TestCase):
    """Tests for the _validate_request method in DentalAppUssdGateway."""

    def setUp(self):
        self.view = DentalAppUssdGateway()

    def test_valid_payload_passes(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': 'sess-001',
            'phoneNumber': '+67570001111',
            'MSG': '*123#',
            'serviceCode': '*123#',
        })
        self.assertEqual(errors, [])
        self.assertIsNotNone(sanitised)

    def test_missing_required_field_returns_errors(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': 'sess-001',
            'phoneNumber': '+67570001111',
            # MSG missing
            'serviceCode': '*123#',
        })
        self.assertTrue(len(errors) > 0)
        self.assertIsNone(sanitised)

    def test_invalid_phone_number_returns_error(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': 'sess-001',
            'phoneNumber': 'not-a-phone',
            'MSG': '*123#',
            'serviceCode': '*123#',
        })
        self.assertTrue(any('phoneNumber' in e for e in errors))
        self.assertIsNone(sanitised)

    def test_msg_too_long_returns_error(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': 'sess-001',
            'phoneNumber': '+67570001111',
            'MSG': 'x' * 201,
            'serviceCode': '*123#',
        })
        self.assertTrue(any('MSG' in e for e in errors))
        self.assertIsNone(sanitised)

    def test_empty_session_id_returns_error(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': '',
            'phoneNumber': '+67570001111',
            'MSG': '*123#',
            'serviceCode': '*123#',
        })
        self.assertTrue(any('sessionId' in e for e in errors))
        self.assertIsNone(sanitised)

    def test_phone_number_stripped_of_plus(self):
        errors, sanitised = self.view._validate_request({
            'sessionId': 'sess-001',
            'phoneNumber': '+67570001111',
            'MSG': '*123#',
            'serviceCode': '*123#',
        })
        self.assertEqual(errors, [])
        # phoneNumber should be preserved as-is in sanitised data
        self.assertEqual(sanitised['phoneNumber'], '+67570001111')

