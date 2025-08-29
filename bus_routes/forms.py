from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, SavedRoute


class CustomUserCreationForm(UserCreationForm):
    """Extended user registration form with additional fields."""
    email = forms.EmailField(required=True, widget=forms.EmailInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))
    phone_number = forms.CharField(max_length=20, required=False, widget=forms.TextInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))
    preferred_language = forms.ChoiceField(choices=[
        ('en', 'English'),
        ('mm', 'Myanmar'),
    ], required=True, widget=forms.Select(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        # Add styling to the default fields
        for field_name in ['username', 'password1', 'password2']:
            self.fields[field_name].widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'
            })

    def save(self, commit=True):
        user = super(CustomUserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            # Create the user profile
            UserProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data.get('phone_number', ''),
                preferred_language=self.cleaned_data.get('preferred_language', 'en')
            )

        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with styled widgets."""
    username = forms.CharField(widget=forms.TextInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'}))


class SavedRouteForm(forms.ModelForm):
    """Form for saving favorite routes."""

    class Meta:
        model = SavedRoute
        fields = ('name', 'start_stop', 'end_stop')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-all duration-200',
                'placeholder': 'e.g., Home to Work'
            }),
        }