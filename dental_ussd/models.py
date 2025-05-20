from django.db import models
from django.core.validators import MinValueValidator

# Create your models here.
class Patient(models.Model):
    mobile_number = models.CharField(max_length=15, unique=True, null=False)
    name = models.CharField(max_length=100, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.mobile_number})"

class Appointment(models.Model):
    user = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    appointment_type = models.CharField(max_length=50, null=False)
    clinic_location = models.CharField(max_length=100, null=False)
    appointment_date = models.DateTimeField(null=False)
    status = models.CharField(
        max_length=20,
        default='Scheduled',
        choices=[('Scheduled', 'Scheduled'), ('Done', 'Done'), ('Cancelled', 'Cancelled')]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.appointment_type} at {self.clinic_location} on {self.appointment_date}"

class ClinicAvailability(models.Model):
    clinic_location = models.CharField(max_length=100, null=False)
    appointment_type = models.CharField(max_length=50, null=False)
    appointment_type = models.CharField(
        max_length=50,
        choices=[
            ('Checkup', 'Checkup'),
            ('Cleaning', 'Cleaning'),
            ('Filling', 'Filling'),
        ],
        null=False
    )
    available_slots = models.IntegerField(null=False, validators=[MinValueValidator(0)])
    appointment_date = models.DateTimeField(null=False)
    last_updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clinic_availability'
        constraints = [
            models.CheckConstraint(check=models.Q(available_slots__gte=0), name='available_slots_non_negative')
        ]

    def __str__(self):
        return f"{self.appointment_type} at {self.clinic_location} on {self.appointment_date}"