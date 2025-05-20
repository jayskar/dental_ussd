import os
import yaml
from django.shortcuts import render
from django.conf import settings

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from ussd.core import UssdEngine, UssdRequest
from ussd.tests.sample_screen_definition import path
from simplekv.fs import FilesystemStore
import structlog

logger = structlog.get_logger(__name__)
# Create your views here.
class CustomUssdRequest(UssdRequest):
    def get_screens(self, screen_name):
        # journey_file = getattr(self, 'journey_file', os.path.join(settings.BASE_DIR, 'journeys', 'sample_customer_journey.yml'))
        journey_file = getattr(self, 'journey_file', settings.DEFAULT_USSD_SCREEN_JOURNEY)
        logger.info(f"Loading journey file: {journey_file}")
        if not os.path.exists(journey_file):
            logger.error(f"Journey file not found: {journey_file}")
            raise FileNotFoundError(f"Journey file not found: {journey_file}")
        with open(journey_file, 'r') as f:
            journey_content = yaml.safe_load(f)
        if not isinstance(journey_content, dict):
            logger.error(f"Invalid journey file format: {journey_file}, expected a dictionary")
            raise ValueError(f"Invalid journey file format: {journey_file}")
        screen_content = journey_content.get(screen_name)
        if screen_content is None:
            logger.error(f"Screen not found: {screen_name} in {journey_file}")
            raise ValueError(f"Screen not found: {screen_name}")
        if not isinstance(screen_content, (dict, str)):
            logger.error(f"Invalid screen content for {screen_name}: {screen_content}, expected dict or str")
            raise ValueError(f"Invalid screen content for {screen_name}")
        return screen_content
    
class DentalUssdGateWay(APIView, UssdEngine):

    def post(self, ussd_request, *args, **kwargs):
        """
        Extract USSD parameters from the request data
        """
        session_id = self.request.data.get('sessionId')
        phone_number = self.request.data.get('phoneNumber')
        ussd_input = self.request.data.get('MSG')
        language = self.request.data.get('language', 'en')
        journey_name = "sample_menu" # DEFAULT_USSD_SCREEN_JOURNEY

        # Validate required parameters
        if not session_id or not phone_number:
            return Response({'status': 'error', 'message': 'Missing required parameters'}, status=400)
        
        try:
            # Initialize UssdRequest object
            ussd_request = CustomUssdRequest(
                session_id=session_id,
                phone_number=phone_number,
                ussd_input=ussd_input,
                language=language,
                journey_name=journey_name, 
                session_store_backend=FilesystemStore("./session_store"),
                default_language='en',
                use_built_in_session_management=False,
                expiry=180
            )
            # Initialize UssdEngine with the UssdRequest object
            ussd_engine = UssdEngine(ussd_request)

            # Process the USSD request
            ussd_response = ussd_engine.ussd_dispatcher()

            # Prepare the response
            response_data = self.ussd_response_handler(ussd_response)
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"UssdEngine error: {str(e)}")
            response = Response({
                'status': 'error',
                'MSG': 'Error processing USSD request',
                'MSGTYPE': 'END'
            }, status=500)
            return response
        
    def ussd_response_handler(self, ussd_response):
        msg_type = 'CON' if ussd_response.status else 'END'
        if self.request.data.get('serviceCode') == 'test':
            msg_type = 'TEST'
        response_data = {
            'status': 'success',
            'MSG': str(ussd_response),
            'MSGTYPE': msg_type
        }
        return response_data
    