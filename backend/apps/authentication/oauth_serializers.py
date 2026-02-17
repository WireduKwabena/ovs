from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.conf import settings
from apps.authentication.utils.base_serializer_auth import (
    get_or_create_user,
    get_tokens_for_user,
    verify_google_token,
    verify_github_code,
)

class BaseOAuthSerializer(serializers.Serializer):
    def get_user_data(self, validated_data, provider=None):
        try:
            print(f"🔍 Starting get_user_data with attrs: {list(validated_data.keys())}")
            
            user_data = validated_data
            print(f"✅ validate() returned: {user_data.get('email')}")
            
            email = user_data.get("email")
            name = user_data.get("name") or user_data.get("login")
            username = email.split("@")[0]
            profile_pic_url = user_data.get('avatar_url') or user_data.get('picture')
            
            print(f"📝 Creating user: email={email}, name={name}, provider={provider}")
                

            with transaction.atomic():
                user = get_or_create_user(
                    email=email,
                    name=name,
                    username=username,
                    provider=provider,
                    profile_picture_url=profile_pic_url if profile_pic_url else None
                )
                print(f"✅ User created/retrieved: {user.email}")

                # Ensure user object is valid before continuing.
                if not user or not user.pk:
                    raise serializers.ValidationError({"error": "Failed to retrieve or create user in DB."})
                
                try:
                    # with transaction.atomic():  # Nested atomic for tokens
                    tokens = get_tokens_for_user(user) # This line caused the error in the traceback
                    print(f"✅ Tokens generated")
                except IntegrityError as e:
                    # Log and fallback (e.g., generate without blacklisting)
                    print(f"Token blacklist error: {e}")
                    # Temporarily disable blacklisting in settings or use a custom token func
                    raise serializers.ValidationError({"error": "Token generation failed due to blacklist issue."})
                


                result = {
                        'user': user,
                        'tokens': tokens,
                        'user_type': 'applicant',
                    }
                print(f"✅ get_user_data completed successfully")
                return result
        except Exception as e:
            print(f"❌ Error in get_user_data: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise serializers.ValidationError({"error": "Authentication failed due to server error."})

class GoogleAuthSerializer(BaseOAuthSerializer):
    code = serializers.CharField()
    redirect_uri = serializers.CharField(required=False)
    provider = serializers.CharField(default="google")

    def validate(self, attrs):
        token = attrs.get("code")
        if not token:
            raise serializers.ValidationError({"error": "Token not provided"})
        redirect_uri = attrs.get("redirect_uri")
        if not redirect_uri:
            redirect_uri = f'{settings.FRONTEND_URL}/login'

        print(f"DEBUG: Received Google token: {token} {redirect_uri}") ## Debug print
        try:
            idinfo = verify_google_token(token, redirect_uri)
            return idinfo
        except ValueError as e:
            raise serializers.ValidationError({"error": f"Invalid Google token:  {str(e)}"})

class GitHubAuthSerializer(BaseOAuthSerializer):
    code = serializers.CharField()
    redirect_uri = serializers.CharField(required=False)
    provider = serializers.CharField(default="github")

    def validate(self, attrs):
        code = attrs.get('code')
        redirect_uri = attrs.get("redirect_uri")
        if not redirect_uri:
            redirect_uri = f'{settings.FRONTEND_URL}/login'
        if not code:
            raise serializers.ValidationError({"error": "Code not provided"})
        try:
            return verify_github_code(code, redirect_uri)
        except ValueError as e:
            raise serializers.ValidationError({"error": f"Invalid GitHub code : {str(e)}"})
