from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from FYP_app.function import get_stock_data




# ---------------- SIGN UP VIEW ----------------
def SignUp_View(request):
    # Check if user submitted the form (POST request)
    if request.method == 'POST':
        # Create a UserCreationForm using posted data
        form = UserCreationForm(request.POST)

        # Check if form inputs are valid
        if form.is_valid():
            # Save the user to the database
            user = form.save()

            # Log in the newly registered user automatically
            login(request, user)

            # Redirect to dashboard page
            return redirect('dashboard')

    else:
        # Initial empty values for form fields
        initial_data = {'username': '', 'password1': '', 'password2': ""}

        # If normal GET request → show empty form
        form = UserCreationForm(initial=initial_data)

    # Render registration page with form
    return render(request, 'Sign_Up.html', {'form': form})



# ---------------- SIGN IN VIEW ----------------
def Sign_In_view(request):
    # If form submitted (POST request)
    if request.method == 'POST':
        # Authentication form checks username + password
        form = AuthenticationForm(request, data=request.POST)

        # If username & password are correct
        if form.is_valid():
            # Get logged-in user object
            user = form.get_user()

            # Log the user into the session
            login(request, user)

            # Redirect to dashboard
            return redirect('dashboard')

    else:
        # Empty initial values for login form
        initial_data = {'username': '', 'password': ''}

        # Create empty login form for GET request
        form = AuthenticationForm(initial=initial_data)

    # Render login page with form
    return render(request, 'Sign_In.html', {'form': form})



# ---------------- DASHBOARD VIEW ----------------
def dashboard_view(request):
    # Simply render the dashboard template
    return render(request, 'Dashboard.html')



# ---------------- LOGOUT VIEW ----------------
def logout_view(request):
    # Log out the current user and clear the session
    logout(request)

    # Redirect to login page after logout
    return redirect('Sign_In')
def forgetPassword(request):
    return(request,'ForgetPassword.html')

def stock(request):
    return(get_stock_data())

