from django.contrib import admin
from .models import Patient, Appointment, ClinicAvailability
# Register your models here.
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile_number', 'created_at', 'updated_at')
    search_fields = ('name', 'mobile_number')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
    list_per_page = 20
    date_hierarchy = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('name', 'mobile_number')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'appointment_type', 'clinic_location', 'appointment_date', 'status', 'created_at', 'updated_at')
    search_fields = ('user__name', 'user__mobile_number', 'appointment_type', 'clinic_location')
    list_filter = ('status', 'appointment_date')
    ordering = ('-created_at',)
    list_per_page = 20
    date_hierarchy = 'appointment_date'
    fieldsets = (
        (None, {
            'fields': ('user', 'appointment_type', 'clinic_location', 'appointment_date', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')  
@admin.register(ClinicAvailability)
class ClinicAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('clinic_location', 'appointment_type', 'available_slots', 'appointment_date', 'last_updated')
    search_fields = ('clinic_location', 'appointment_type')
    list_filter = ('appointment_date',)
    ordering = ('-last_updated',)
    list_per_page = 20
    date_hierarchy = 'last_updated'
    fieldsets = (
        (None, {
            'fields': ('clinic_location', 'appointment_type', 'available_slots', 'appointment_date')
        }),
        ('Timestamps', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('last_updated',)
    