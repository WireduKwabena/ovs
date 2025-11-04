from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
# only authenticated users can access this view
@login_required(login_url='auth_actions:login')
def home_view(request):
    return render(request, 'main_actions/homepage.html')



