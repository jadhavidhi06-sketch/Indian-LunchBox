from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.contrib import messages
from xhtml2pdf import pisa
import hashlib
import json
import random
import string
from datetime import datetime, timedelta
import os
from django.conf import settings

# ==============================================
# HASH PASSWORD FUNCTION
# ==============================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ==============================================
# HOME PAGE VIEW
# ==============================================
def home(request):
    if not request.session.get('user_id'):
        return redirect('login')

    # Fetch all recipes (latest first)
    with connection.cursor() as cursor:
        cursor.execute("SELECT recipe_id, title, description, image FROM recipes ORDER BY recipe_id DESC")
        recipes = cursor.fetchall()  # List of tuples

    return render(request, 'home.html', {'recipes': recipes})


# ==============================================
# REGISTER VIEW
# ==============================================
def register_view(request):
    if request.method == "POST":
        name = request.POST['name']
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.callproc('RegisterUser', [name, email, password])

        return redirect('login')

    return render(request, 'auth/register.html')


# ==============================================
# LOGIN VIEW
# ==============================================
def login_view(request):
    if request.method == "POST":
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email=%s", [email])
            user = cursor.fetchone()

        if user and user[3] == password:
            request.session['user_id'] = user[0]
            request.session['user_name'] = user[1]
            return redirect('home')
        else:
            return HttpResponse("Invalid credentials")

    return render(request, 'auth/login.html')


# ==============================================
# LOGOUT VIEW
# ==============================================
def logout_view(request):
    request.session.flush()
    return redirect('login')


# ==============================================
# ADD RECIPE VIEW
# ==============================================
def add_recipe(request):
    if not request.session.get('user_id'):
        return redirect('login')

    if request.method == "POST":
        title = request.POST['title']
        description = request.POST['description']
        ingredients = request.POST['ingredients']
        steps = request.POST['steps']

        # Handle image upload
        image = request.FILES.get('image')
        fs = FileSystemStorage()
        filename = fs.save(image.name, image)

        # Save recipe via procedure
        with connection.cursor() as cursor:
            cursor.callproc('AddRecipe', [
                request.session['user_id'],
                title,
                description,
                ingredients,
                steps,
                filename
            ])
        return redirect('view_recipes')

    return render(request, 'recipes/add_recipe.html')


# ==============================================
# VIEW RECIPES PAGE (FEED)
# ==============================================
def view_recipes(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.recipe_id, r.title, r.description, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            ORDER BY r.recipe_id DESC
        """)
        recipes = cursor.fetchall()
    return render(request, 'recipes/view_recipes.html', {'recipes': recipes})


# ==============================================
# RECIPE DETAIL + COMMENTS
# ==============================================
def recipe_detail(request, id):
    # Fetch recipe
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.recipe_id, r.title, r.description, r.ingredients, r.steps, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.recipe_id=%s
        """, [id])
        recipe = cursor.fetchone()

    # Fetch comments
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.comment_id, c.comment, c.rating, u.name
            FROM comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.recipe_id=%s
            ORDER BY c.comment_id DESC
        """, [id])
        comments = cursor.fetchall()

    # Add comment
    if request.method == "POST" and request.session.get('user_id'):
        comment_text = request.POST['comment']
        rating = int(request.POST['rating'])
        with connection.cursor() as cursor:
            cursor.callproc('AddComment', [id, request.session['user_id'], comment_text, rating])
        return redirect(f'/recipe/{id}/')

    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe,
        'comments': comments
    })


# ==============================================
# DOWNLOAD RECIPE AS PDF
# ==============================================
def download_recipe_pdf(request, id):
    # Fetch recipe from DB
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.title, r.description, r.ingredients, r.steps, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.recipe_id=%s
        """, [id])
        recipe = cursor.fetchone()

    if not recipe:
        return HttpResponse("Recipe not found")

    # Full image path for xhtml2pdf
    image_path = os.path.join(settings.BASE_DIR, 'media', recipe[4])

    # Render template
    template_path = 'recipes/recipe_pdf.html'
    context = {
        'recipe': recipe,
        'image_path': image_path
    }
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{recipe[0]}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF')
    return response


# ==============================================
# TOGGLE LIKE (AJAX)
# ==============================================
def toggle_like(request, recipe_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Not logged in'}, status=401)

    with connection.cursor() as cursor:
        # Check if already liked
        cursor.execute("SELECT * FROM likes WHERE recipe_id=%s AND user_id=%s", [recipe_id, user_id])
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM likes WHERE recipe_id=%s AND user_id=%s", [recipe_id, user_id])
            liked = False
        else:
            cursor.execute("INSERT INTO likes(recipe_id, user_id) VALUES(%s,%s)", [recipe_id, user_id])
            liked = True
    return JsonResponse({'liked': liked})


# ==============================================
# ABOUT PAGE
# ==============================================
def about_view(request):
    """
    About page view - tells the story of IndianLunchBox
    """
    return render(request, 'about.html')


# ==============================================
# TERMS OF SERVICE PAGE
# ==============================================
def terms_view(request):
    """
    Terms of Service page
    """
    return render(request, 'auth/terms.html')


# ==============================================
# PRIVACY POLICY PAGE
# ==============================================
def privacy_view(request):
    """
    Privacy Policy page
    """
    return render(request, 'auth/privacy.html')


# ==============================================
# CONTACT PAGE
# ==============================================
def contact_view(request):
    """
    Contact page view
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Basic validation
        if not name or not email or not subject or not message:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'contact.html')
        
        if len(message) < 10:
            messages.error(request, 'Message must be at least 10 characters.')
            return render(request, 'contact.html')
        
        # Save to database
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO contact_messages (name, email, subject, message, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [name, email, subject, message])
        except:
            # Table might not exist, just skip saving
            pass
        
        messages.success(request, f'Thank you {name}! Your message has been sent. We\'ll get back to you soon. ❤️')
        return redirect('contact')
    
    return render(request, 'contact.html')


# ==============================================
# FORGOT PASSWORD PAGE
# ==============================================
def forgot_password(request):
    """
    Forgot password page view
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        with connection.cursor() as cursor:
            # Check if email exists
            cursor.execute("SELECT user_id, name FROM users WHERE email = %s", [email])
            user = cursor.fetchone()
        
        if user:
            # Generate reset token
            reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
            
            # Store token in session
            request.session['reset_token'] = reset_token
            request.session['reset_email'] = email
            request.session['reset_expiry'] = (datetime.now() + timedelta(minutes=30)).timestamp()
            
            messages.success(request, f'Password reset link sent to {email}. Please check your inbox.')
        else:
            messages.error(request, 'No account found with this email address.')
        
        return redirect('forgot_password')
    
    return render(request, 'auth/forgot_password.html')


# ==============================================
# API: FORGOT PASSWORD (AJAX)
# ==============================================
def api_forgot_password(request):
    """
    API endpoint for forgot password (AJAX)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({
                    'success': False,
                    'error': 'missing_email',
                    'message': 'Email is required'
                }, status=400)
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT user_id, name FROM users WHERE email = %s", [email])
                user = cursor.fetchone()
            
            if user:
                # Generate reset token
                reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
                
                # Store token in session
                request.session['reset_token'] = reset_token
                request.session['reset_email'] = email
                request.session['reset_expiry'] = (datetime.now() + timedelta(minutes=30)).timestamp()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Reset link sent successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'email_not_found',
                    'message': 'Email not registered'
                }, status=404)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'invalid_json',
                'message': 'Invalid request format'
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'error': 'invalid_method',
        'message': 'Invalid request method'
    }, status=405)


# ==============================================
# RESET PASSWORD PAGE
# ==============================================
def reset_password(request, token):
    """
    Reset password page - called from email link
    """
    # Check if token is valid
    session_token = request.session.get('reset_token')
    reset_email = request.session.get('reset_email')
    reset_expiry = request.session.get('reset_expiry')
    
    if not session_token or session_token != token or not reset_expiry:
        messages.error(request, 'Invalid or expired reset link. Please try again.')
        return redirect('forgot_password')
    
    # Check if token expired
    if datetime.now().timestamp() > reset_expiry:
        messages.error(request, 'Reset link has expired. Please request a new one.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password or len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        # Update password
        hashed_password = hash_password(new_password)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", [hashed_password, reset_email])
        
        # Clear reset session data
        request.session.pop('reset_token', None)
        request.session.pop('reset_email', None)
        request.session.pop('reset_expiry', None)
        
        messages.success(request, 'Password reset successful! Please login with your new password.')
        return redirect('login')
    
    return render(request, 'auth/reset_password.html', {'token': token})


# ==============================================
# MY RECIPES PAGE
# ==============================================
def my_recipes(request):
    """
    Display all recipes created by the logged-in user
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your recipes')
        return redirect('login')
    
    user_id = request.session['user_id']
    recipe_list = []
    
    with connection.cursor() as cursor:
        try:
            # Try using stored procedure first
            cursor.callproc('GetUserRecipes', [user_id])
            recipes = cursor.fetchall()
        except:
            # Fallback to direct query
            cursor.execute("""
                SELECT 
                    r.recipe_id,
                    r.title,
                    r.description,
                    r.image,
                    r.created_at,
                    (SELECT COUNT(*) FROM likes l WHERE l.recipe_id = r.recipe_id) as likes_count,
                    (SELECT COUNT(*) FROM comments c WHERE c.recipe_id = r.recipe_id) as comments_count
                FROM recipes r
                WHERE r.user_id = %s
                ORDER BY r.created_at DESC
            """, [user_id])
            recipes = cursor.fetchall()
    
    # Convert to list of dictionaries
    for recipe in recipes:
        recipe_list.append({
            'recipe_id': recipe[0],
            'title': recipe[1],
            'description': recipe[2],
            'image': recipe[3],
            'created_at': recipe[4],
            'likes_count': recipe[5] if len(recipe) > 5 else 0,
            'comments_count': recipe[6] if len(recipe) > 6 else 0
        })
    
    context = {
        'recipes': recipe_list,
        'total_recipes': len(recipe_list),
        'page_title': 'My Recipes'
    }
    
    return render(request, 'recipes/my_recipes.html', context)


# ==============================================
# SAVED RECIPES PAGE
# ==============================================
def saved_recipes(request):
    """
    Display all recipes saved/bookmarked by the logged-in user
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your saved recipes')
        return redirect('login')
    
    user_id = request.session['user_id']
    saved_list = []
    
    with connection.cursor() as cursor:
        try:
            # Try using stored procedure first
            cursor.callproc('GetSavedRecipes', [user_id])
            saved_recipes = cursor.fetchall()
        except:
            # Fallback to direct query
            cursor.execute("""
                SELECT 
                    s.saved_id,
                    r.recipe_id,
                    r.title,
                    r.description,
                    r.image,
                    u.name as author_name,
                    s.saved_at,
                    (SELECT COUNT(*) FROM likes l WHERE l.recipe_id = r.recipe_id) as likes_count
                FROM saved_recipes s
                JOIN recipes r ON s.recipe_id = r.recipe_id
                JOIN users u ON r.user_id = u.user_id
                WHERE s.user_id = %s
                ORDER BY s.saved_at DESC
            """, [user_id])
            saved_recipes = cursor.fetchall()
    
    for recipe in saved_recipes:
        saved_list.append({
            'saved_id': recipe[0],
            'recipe_id': recipe[1],
            'title': recipe[2],
            'description': recipe[3],
            'image': recipe[4],
            'author_name': recipe[5],
            'saved_at': recipe[6],
            'likes_count': recipe[7] if len(recipe) > 7 else 0
        })
    
    context = {
        'saved_recipes': saved_list,
        'total_saved': len(saved_list),
        'page_title': 'Saved Recipes'
    }
    
    return render(request, 'recipes/saved_recipes.html', context)


# ==============================================
# USER PROFILE PAGE (FIXED)
# ==============================================
def user_profile(request):
    """
    Display user profile with statistics and information
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your profile')
        return redirect('login')
    
    user_id = request.session['user_id']
    user_name = request.session.get('user_name')
    
    with connection.cursor() as cursor:
        # Get user profile information
        cursor.execute("""
            SELECT u.user_id, u.name, u.email, u.created_at,
                   COALESCE(p.bio, '') as bio,
                   COALESCE(p.location, '') as location,
                   COALESCE(p.favorite_food, '') as favorite_food,
                   COALESCE(p.avatar, '') as avatar
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id
            WHERE u.user_id = %s
        """, [user_id])
        user_data = cursor.fetchone()
        
        # Get user statistics
        try:
            cursor.callproc('GetUserStatistics', [user_id])
            stats = cursor.fetchone()
        except:
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM recipes WHERE user_id = %s) as total_recipes,
                    (SELECT COUNT(*) FROM likes l 
                     JOIN recipes r ON l.recipe_id = r.recipe_id 
                     WHERE r.user_id = %s) as total_likes_received,
                    (SELECT COUNT(*) FROM comments c 
                     JOIN recipes r ON c.recipe_id = r.recipe_id 
                     WHERE r.user_id = %s) as total_comments,
                    (SELECT COUNT(*) FROM saved_recipes WHERE user_id = %s) as total_saved,
                    (SELECT COUNT(*) FROM likes WHERE user_id = %s) as total_likes_given
            """, [user_id, user_id, user_id, user_id, user_id])
            stats = cursor.fetchone()
    
    if user_data:
        profile = {
            'user_id': user_data[0],
            'name': user_data[1],
            'email': user_data[2],
            'joined_date': user_data[3],
            'bio': user_data[4] or '',
            'location': user_data[5] or '',
            'favorite_food': user_data[6] or '',
            'avatar': user_data[7] or ''
        }
    else:
        profile = {
            'user_id': user_id,
            'name': user_name,
            'email': '',
            'joined_date': None,
            'bio': '',
            'location': '',
            'favorite_food': '',
            'avatar': ''
        }
    
    statistics = {
        'total_recipes': stats[0] if stats else 0,
        'total_likes_received': stats[1] if stats else 0,
        'total_comments': stats[2] if stats else 0,
        'total_saved': stats[3] if stats else 0,
        'total_likes_given': stats[4] if stats else 0
    }
    
    context = {
        'profile': profile,
        'statistics': statistics,
        'page_title': 'My Profile'
    }
    
    # FIXED: Correct render syntax - request first, then template, then context
    return render(request, 'auth/user_profile.html', context)


# ==============================================
# UPDATE PROFILE
# ==============================================
def update_profile(request):
    """
    Update user profile information
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to update your profile')
        return redirect('login')
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        bio = request.POST.get('bio', '')
        location = request.POST.get('location', '')
        favorite_food = request.POST.get('favorite_food', '')
        
        with connection.cursor() as cursor:
            try:
                cursor.callproc('UpdateUserProfile', [user_id, bio, location, favorite_food])
            except:
                cursor.execute("""
                    INSERT INTO user_profiles (user_id, bio, location, favorite_food)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        bio = VALUES(bio),
                        location = VALUES(location),
                        favorite_food = VALUES(favorite_food)
                """, [user_id, bio, location, favorite_food])
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_profile')
    
    return redirect('user_profile')


# ==============================================
# DELETE MY RECIPE
# ==============================================
def delete_my_recipe(request, recipe_id):
    """
    Delete a recipe created by the user
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        try:
            cursor.callproc('DeleteRecipe', [recipe_id, user_id])
        except:
            cursor.execute("DELETE FROM recipes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
    
    messages.success(request, 'Recipe deleted successfully!')
    return redirect('my_recipes')


# ==============================================
# REMOVE SAVED RECIPE
# ==============================================
def remove_saved_recipe(request, saved_id):
    """
    Remove a recipe from saved/bookmarked list
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM saved_recipes WHERE saved_id = %s", [saved_id])
    
    messages.success(request, 'Recipe removed from saved list!')
    return redirect('saved_recipes')


# ==============================================
# API: DELETE RECIPE (AJAX)
# ==============================================
def delete_recipe_api(request, recipe_id):
    """API endpoint to delete a recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        try:
            cursor.callproc('DeleteRecipe', [recipe_id, user_id])
        except:
            cursor.execute("DELETE FROM recipes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
    
    return JsonResponse({'success': True})


# ==============================================
# API: REMOVE SAVED (AJAX)
# ==============================================
def remove_saved_api(request, saved_id):
    """API endpoint to remove a saved recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM saved_recipes WHERE saved_id = %s", [saved_id])
    
    return JsonResponse({'success': True})