from django.forms import ModelForm
from django import forms
from .models import CustomUser as User


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
        label='Username'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
        label='Password'
    )

class RegistrationForm(ModelForm):
    class Meta:
        model = User
        fields = ['first_name','last_name','username', 'email', 'password','birth_date','bio']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
            'last_name': forms.TextInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
            'username': forms.TextInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
            'email': forms.EmailInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
            'password': forms.PasswordInput(attrs={'class': 'form-control mb-2 p-2 border border-gray-300 input '}),
            'birth_date': forms.TextInput(attrs={'class':'form-control input mb-2 p-2 border border-gray-300 ','type':'date'}),
            #TextArea input for bio 
            'bio':forms.Textarea(attrs={'class':'form-control textarea mb-2 p-2 border border-gray-300', 'placeholder':'Something about yourself', 'rows':5})
            
            
        }
        labels = {
            'first_name':'First Name',
            'last_name':'Last Name',
            'username': 'Username',
            'email': 'Email',
            'password': 'Password',
            'birth_date':'Date of Birth',
            'bio':'Bio'
        }