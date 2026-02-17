from apps.authentication.oauth_serializers import GoogleAuthSerializer, GitHubAuthSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import generics, status

class GoogleLoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GoogleAuthSerializer

    def post(self, request, *args, **kwargs):
        print(f"📥 Received request data: {request.data}")
        
        serializer = self.serializer_class(data=request.data)
        
        if not serializer.is_valid():
            print("❌ VALIDATION ERROR:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user data
            user_data = serializer.get_user_data(serializer.validated_data, provider=request.data.get('provider'))
            print(f"✅ User authenticated: {user_data['user'].email}")
            
            # Serialize the response properly
            response_data = {
                'user': {
                    'email': user_data['user'].email,
                    'full_name': user_data['user'].get_full_name(),
                    'id': user_data['user'].id,
                },
                'tokens': user_data['tokens'],
                'user_type': user_data['user_type']
            }
            
            print(f"✅ Sending response: {response_data['user']['email']}")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error in view: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )



class GitHubLoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GitHubAuthSerializer


    def post(self, request, *args, **kwargs):
        print(f"📥 Received request data: {request.data}")

        serializer = self.serializer_class(data=request.data)
        
        if not serializer.is_valid():
            print("❌ VALIDATION ERROR:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user data
            user_data = serializer.get_user_data(serializer.validated_data, provider=request.data.get('provider'))
            print(f"✅ User authenticated: {user_data['user'].email}")


            # Serialize the response properly
            response_data = {
                'user': {
                    'email': user_data['user'].email,
                    'full_name': user_data['user'].get_full_name(),
                    'id': user_data['user'].id,
                },
                'tokens': user_data['tokens'],
                'user_type': user_data['user_type']
            }
            
            print(f"✅ Sending response: {response_data['user']['email']}")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error in view: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    
    
