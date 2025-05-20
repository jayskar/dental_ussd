from django.urls import path

from .views import DentalUssdGateWay ##, my_ussd_view #, UssdAPIView

app_name = "ussd"
urlpatterns = [
    path("dental_ussd_gw/", DentalUssdGateWay.as_view(), name="dental_ussd_gw"),
    # path('ussd/', UssdAPIView.as_view(), name='ussd-api'),
]
