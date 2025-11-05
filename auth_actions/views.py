from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
# from django.contrib.auth.decorators 

from auth_actions.forms import LoginForm, RegistrationForm



def unauthenticated_user_required(view_func):
    """
    Decorator that redirects authenticated users to settings.LOGIN_REDIRECT_URL
    (or '/home/' if not set).
    """
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            # If the user is logged in, redirect them away
            return redirect(settings.LOGIN_REDIRECT_URL or 'main_actions:home')
        else:
            # If not logged in, proceed to the view function (login/signup)
            return view_func(request, *args, **kwargs)
    return wrapper_func
# Create your views here.


@unauthenticated_user_required
@require_http_methods(["GET", "POST"])
def login_view(request):
    next_page =  request.GET.get("next")
    form = LoginForm()
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if next_page:
                    return redirect(next_page)
                return redirect('main_actions:home')
            else:
                form.add_error(None, "Invalid username or password.")
    
    
    
    return render(request, 'auth_actions/login.html', {'form': form})




@require_http_methods(["GET", "POST"])
def register_view(request):
    # 1. Initialize the form outside all conditional blocks
    # This ensures 'register_form' is always defined.
    register_form = RegistrationForm() 

    if request.method == 'POST':
        # 2. If it's a POST, create a form instance with the submitted data
        register_form = RegistrationForm(request.POST) 

        if register_form.is_valid():
            # 3. If valid, save the data and redirect
            user = register_form.save(commit=False)
            user.set_password(register_form.cleaned_data['password'])
            user.save()
            
            messages.success(request, 'Account created successfully!')
            login(request, user)
            return redirect('main_actions:home')  # Replace 'home' with your desired redirect URL

        # If the form is *not* valid, the code continues to the return statement, 
        # using the 'register_form' that now contains the errors.

    # 4. For a GET request, or a POST with errors, render the template
    return render(request, 'auth_actions/register.html', {'register_form': register_form})


@require_http_methods(["GET"])
def logout_view(request):
    logout(request)
    return redirect('auth_actions:login')


# class UserCreateView(CreateView):
#     form_class = UserCreationForm
#     template_name = 'auth_actions/register.html'
    
    
    