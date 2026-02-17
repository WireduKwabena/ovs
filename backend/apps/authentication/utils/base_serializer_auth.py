import requests
import jwt
from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from apps.authentication.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from oauth2client import client
import urllib.parse



def verify_google_token(token, redirect_uri=None):
     # Remove the debug print that shows token as tuple
    print(f"DEBUG: Received code: {token}")
    print(f"DEBUG: Redirect URI: {redirect_uri}")
    print(f"DEBUG: Client ID: {settings.GOOGLE_CLIENT_ID}")
    print(f"DEBUG: Client Secret (First 5 chars): {str(settings.GOOGLE_CLIENT_SECRET)[:10]}...")
    
    
    try:
        # Step 1: Exchange authorization code for tokens
        token_uri = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": token,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        
        body = urllib.parse.urlencode(payload)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(token_uri, data=body, headers=headers)
        
        print(f"Google Token Response Status: {response.status_code}")
        print(f"Google Token Response Body: {response.json()}")
        
        if response.status_code != 200:
            raise serializers.ValidationError({
                "error": "Failed to retrieve tokens from Google",
                "details": response.json()
            })
        
        response_data = response.json()
        print(f"✅ Successfully got tokens from Google")
        
        # Check for error in response
        if 'error' in response_data:
            raise serializers.ValidationError({
                "error": "Google rejected the code",
                "details": response_data.get('error_description')
            })
        
        id_token_str = response_data.get("id_token")
        
        if not id_token_str:
            raise serializers.ValidationError({"error": "ID token not found in Google response"})
        
        # Step 2: Verify the ID token with Google's official library (SECURE ✅)
        decoded_token = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10  # Allow 10 seconds clock skew
        )
        
        # Verify the audience supports both client IDs
        if decoded_token.get('aud') not in [settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_ID_2]:
            raise serializers.ValidationError({"error": "Invalid token audience"})
        
        print(f"✅ Token verified successfully for: {decoded_token.get('email')}")
    
        return decoded_token
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        raise serializers.ValidationError({"error": f"Failed to connect to Google: {str(e)}"})
    except ValueError as e:
        # This catches Google's token verification errors
        print(f"Token verification error: {str(e)}")
        raise serializers.ValidationError({"error": "Invalid or expired Google token"})
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise serializers.ValidationError({"error": f"Token verification failed: {str(e)}"})


def verify_github_code(code, redirect_uri=None):
    # In auth_actions/utils/base_serializer_auth.py
    print(f"DEBUG: Client ID: {settings.GITHUB_CLIENT_ID}")
    print(f"DEBUG: Client Secret (First 5 chars): {str(settings.GITHUB_CLIENT_SECRET)[:10]}...")
    
    token_url = "https://github.com/login/oauth/access_token"
    params = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET,
        'code': code,
         'redirect_uri': redirect_uri,
    }
    headers = {'content-type': 'application/json', 'Accept': 'application/json'}
    response = requests.post(token_url, params=params, headers=headers)

    # Debug print to see what GitHub actually says
    print(f"GitHub Token Response: {response.json()}") 

    if response.status_code != 200:
        raise serializers.ValidationError({"error": "Failed to retrieve access token from GitHub"})

    response_data = response.json()

    # GitHub returns 200 OK even on error, but includes an 'error' key.
    if 'error' in response_data:
        raise serializers.ValidationError({
            "error": "GitHub rejected the code", 
            "details": response_data.get('error_description')
        })

    access_token = response_data.get('access_token')
    # if not access_token:
    #     raise serializers.ValidationError({"error": "Access token not found in GitHub response"})

    user_data_url = "https://api.github.com/user"
    user_headers = {'Authorization': f'Bearer {access_token}'}
    user_response = requests.get(user_data_url, headers=user_headers)
    
    if user_response.status_code != 200:
        print(f"GitHub Profile Fetch Status: {user_response.status_code}") # <-- Add this line
        raise serializers.ValidationError({"error": "Failed to fetch user profile"})

    user_data = user_response.json()

    if not user_data.get('email'):
        emails_response = requests.get(f"{user_data_url}/emails", headers=user_headers)
        if emails_response.status_code == 200:
            emails = emails_response.json()
            # Find the primary email
            primary_email = next((e['email'] for e in emails if e['primary']), None)
            user_data['email'] = primary_email

    if not user_data.get('email'):
        raise serializers.ValidationError({"error": "GitHub account has no verified primary email"})

    return user_data

@transaction.atomic
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

@transaction.atomic
def get_or_create_user(email, name, username=None, provider=None, profile_picture_url=None):
    try:
        user, created = User.objects.get_or_create(email=email)
        if created:
            user.set_unusable_password()
            # Split name into first and last name if possible
            if name:
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                if len(name_parts) > 1:
                    user.last_name = name_parts[1]
            
            # Assuming registration_method and profile_picture_url are not in the User model based on previous read_file
            # If they are needed, they should be added to the User model or UserProfile model
            # For now, I will comment them out to avoid errors if they don't exist
            # user.registration_method = provider
            # user.profile_picture_url = profile_picture_url
            user.save()
            
        # elif user.registration_method not in ['google', 'github']:
        #     raise serializers.ValidationError({
        #         "error": "User needs to sign in through email",
        #         "status": False
        #     })
        return user
    except Exception as e:
        raise serializers.ValidationError({"error": str(e)})
