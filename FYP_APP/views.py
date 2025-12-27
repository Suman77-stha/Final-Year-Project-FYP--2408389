from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from FYP_APP.function import get_stock_data
from django.contrib.auth import views as auth_views
from FYP_APP.models import CustomUserCreationForm


from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings



def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        print(email)
        if User.objects.filter(email = email).exists():
            print(email)
            user = User.objects.get(email = email)
            print("User Exists")
            send_mail('Hi',f'user:{user.username},\n\nClick the link below to reset your password:\nhttp://127.0.0.1:8000/password_reset_confirm/{user}',settings.EMAIL_HOST_USER,[email],fail_silently=False)
            return redirect('password_reset_done')
        else:
            print('User Doesnt exit')
            return render(request, 'forgetPassword.html')
    else:
        print('suman 2')
        return render(request, 'forgetPassword.html')

                

def password_Reset_Done_View(request):
    return redirect('password_reset_done')
       
           


def password_reset_confirm(request, user):
    userid = User.objects.get(username = user)
    print("user id: ",userid)
    if request.method == "POST":
        pass1  = request.POST.get("password1")
        pass2  = request.POST.get("password2")
        if pass1 == pass2:
            userid.set_password(pass1)
            userid.save()
            # return HttpResponse("password Reset")
    

    return render(request, 'password_reset_confirm.html')


def password_reset_complete_view(request):
    return redirect('password_reset_complete.html')


# # ---------------- SIGN UP VIEW ----------------
def SignUp_View(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            username = request.POST.get("username")
            email = request.POST.get("email")
            pass1 = request.POST.get("password1")
            pass2 = request.POST.get("password2")

            if pass1 != pass2:
                return render(request, 'Sign_Up.html', {
                    'form': form,
                    'error': 'Passwords do not match'
                })

            if User.objects.filter(username=username).exists():
                return render(request, 'Sign_Up.html', {
                    'form': form,
                    'error': f'Username "{username}" already exists'
                })

            if User.objects.filter(email=email).exists():
                return render(request, 'Sign_Up.html', {
                    'form': form,
                    'error': f'Email "{email}" already exists'
                })

            # ✅ Save user
            user = form.save()
            login(request, user)
            return redirect('dashboard')

    else:
        form = CustomUserCreationForm()

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


def stock(request):
    return(get_stock_data())

